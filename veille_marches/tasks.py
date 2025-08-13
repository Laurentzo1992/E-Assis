from celery import shared_task
from django.db import transaction
import pdfplumber
import re
import json
import time
from .models import Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot
from entreprise.models import Entreprise
from .utils import call_gemini_api
from .prompts import create_extraction_prompt


def _segmenter_document_en_notices(texte_complet: str) -> list[str]:
    if not texte_complet: return []
    pattern_debut = r'(?=\n(?:MINISTERE|AGENCE|ECOLE|CENTRE|COMMUNE|REGION|DIRECTION|PROGRAMME)\s+DE[S\sA-Z]+|\n(?:Résultats\s+provisoires|RESULTATS\s+PROVISOIRES|Demande\s+de\s+prix\s+N°|AVIS\sA\sMANIFESTATION\sD\'INTERET|Appel\s+d\'Offres\s+Ouvert|Base\s+de\s+données\s+complémentaires))'
    notices_candidates = re.split(pattern_debut, texte_complet)
    return [notice.strip() for notice in notices_candidates if notice and len(notice.strip()) > 200]

@transaction.atomic
def _sauvegarder_donnees_notice(data: dict, publication: Publication):
    """
    Sauvegarde les données d'une notice. Tente de lier les lots à des entreprises
    existantes mais n'en crée aucune.
    """
    #création de TypeProcedure, Marche, AppelOffre/Resultat)
    type_proc_libelle = data.get('type_procedure')
    if not type_proc_libelle: return
    type_proc, _ = TypeProcedure.objects.get_or_create(libelle=type_proc_libelle)
    marche_data = data.get('marche', {})
    marche = Marche.objects.create(publication=publication, type_procedure=type_proc, **marche_data)
    if data.get('appel_offre'): AppelOffre.objects.create(marche=marche, **data['appel_offre'])
    if data.get('resultat'):
        champs_resultat = {k: v for k, v in data['resultat'].items() if k in ['date_attribution', 'reference_decision', 'nombre_offres_recues', 'delai_execution']}
        Resultat.objects.create(marche=marche, **champs_resultat)

    # --- GESTION DES LOTS ---
    for lot_info in data.get('lots', []):
        nom_entreprise_brut = lot_info.get('nom_entreprise')
        if not nom_entreprise_brut:
            continue

        entreprise_obj = None # Initialiser à None
        try:
            # On tente de trouver l'entreprise par son nom.
            # `iexact` est insensible à la casse pour plus de flexibilité.
            entreprise_obj = Entreprise.objects.get(nom__iexact=nom_entreprise_brut.strip())
            print(f"Entreprise trouvée : {entreprise_obj.nom}")
        except Entreprise.DoesNotExist:
            # Si l'entreprise n'est pas trouvée, on ne fait rien.
            # `entreprise_obj` reste à None.
            print(f"Avertissement : L'entreprise '{nom_entreprise_brut.strip()}' n'existe pas dans la base de données. Le lot sera créé sans lien.")
            pass
        
        # On supprime la clé qui n'est pas dans notre modèle Lot
        lot_info.pop('nom_entreprise', None) 
        
        # On crée le lot, en liant l'entreprise si elle a été trouvée.
        Lot.objects.create(
            marche=marche,
            entreprise_concernee=entreprise_obj, # Sera None si non trouvée
            nom_entreprise_texte=nom_entreprise_brut.strip(), # On sauvegarde toujours le nom brut
            numero_lot=lot_info.get('numero_lot'),
            description=lot_info.get('description'),
            montant_propose=lot_info.get('montant_propose'),
            statut=lot_info.get('statut', 'AUTRE').upper().replace(" ", "_"),
            rang=lot_info.get('rang'),
            motif=lot_info.get('motif')
        )   

@shared_task(bind=True)
def process_publication_pipeline(self, publication_id: int):
    """
    Tâche Celery principale qui orchestre le traitement complet d'une publication.
    """
    try:
        publication = Publication.objects.get(id=publication_id)
        if publication.status == Publication.Status.COMPLETED:
            return f"Publication {publication_id} déjà traitée."
            
        publication.status = Publication.Status.PROCESSING
        publication.save()

        texte_complet = ""
        with pdfplumber.open(publication.fichier_pdf.path) as pdf:
            for page in pdf.pages:
                texte_page = page.extract_text(x_tolerance=2, y_tolerance=2)
                if texte_page:
                    texte_complet += texte_page + "\n\n"
        
        if not texte_complet.strip():
            raise ValueError("Le contenu extrait du PDF est vide.")

        notices_candidates = _segmenter_document_en_notices(texte_complet)
        
        i = 0
        while i < len(notices_candidates):
            # --- AJOUT DE LA TEMPORISATION ---
            # Ajoute une pause de 5 secondes avant chaque appel à l'API
            # pour respecter les limites de requêtes par minute.
            time.sleep(5)

            notice_actuelle = notices_candidates[i]
            prompt = create_extraction_prompt(notice_actuelle)
            reponse_str = call_gemini_api(prompt)
            
            if not reponse_str:
                i += 1
                continue
            
            try:
                json_match = re.search(r'\{.*\}', reponse_str, re.DOTALL)
                if not json_match:
                     raise json.JSONDecodeError("Aucun objet JSON trouvé", reponse_str, 0)
                
                donnees = json.loads(json_match.group(0))

                if donnees.get("estComplet") is True:
                    _sauvegarder_donnees_notice(donnees, publication)
                    i += 1
                elif donnees.get("estComplet") is False:
                    if i + 1 < len(notices_candidates):
                        notices_candidates[i+1] = notice_actuelle + "\n\n" + notices_candidates[i+1]
                    i += 1
                else:
                    i += 1
            
            except json.JSONDecodeError:
                i += 1
        
        publication.status = Publication.Status.COMPLETED
        publication.save()
        return f"Traitement de la publication {publication_id} terminé."

    except Publication.DoesNotExist:
        return f"Échec: Publication {publication_id} non trouvée."
    except Exception as e:
        try:
            publication = Publication.objects.get(id=publication_id)
            publication.status = Publication.Status.ERROR
            publication.save()
        except Publication.DoesNotExist:
            pass
        raise e 