from celery import shared_task
from django.db import transaction
import pdfplumber
import re
import json
import time
from backend.models import Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot, Notification
from entreprise.models import Entreprise, Domaine
from .utils import call_gemini_api
from .prompts import create_extraction_prompt


def segmenter_document_en_notices(texte_complet: str) -> list[str]:
    if not texte_complet: return []
    pattern_debut = r'(?=\n(?:MINISTERE|AGENCE|ECOLE|CENTRE|COMMUNE|REGION|DIRECTION|PROGRAMME)\s+DE[S\sA-Z]+|\n(?:Résultats\s+provisoires|RESULTATS\s+PROVISOIRES|Demande\s+de\s+prix\s+N°|AVIS\sA\sMANIFESTATION\sD\'INTERET|Appel\s+d\'Offres\s+Ouvert|Base\s+de\s+données\s+complémentaires))'
    notices_candidates = re.split(pattern_debut, texte_complet)
    return [notice.strip() for notice in notices_candidates if notice and len(notice.strip()) > 200]

def extraire_domaine_avec_ia(notice_text: str) -> str:
    """
    Utilise l'IA pour identifier le domaine d'activité d'une notice
    en comparant avec les domaines disponibles dans la base de données.
    """
    try:
        # Récupérer tous les domaines disponibles
        domaines_disponibles = list(Domaine.objects.values_list('libelle', flat=True))
        
        if not domaines_disponibles:
            return None
            
        # Créer un prompt spécifique pour l'identification des domaines
        prompt_domaine = f"""
Analysez cette notice de marché public et identifiez le domaine d'activité correspondant.

DOMAINES DISPONIBLES:
{', '.join(domaines_disponibles)}

INSTRUCTIONS:
- Retournez UNIQUEMENT le nom exact du domaine qui correspond le mieux à cette notice
- Si aucun domaine ne correspond, retournez "AUCUN"
- Réponse au format JSON strict: {{"domaine": "nom_du_domaine"}}

NOTICE À ANALYSER:
{notice_text[:2000]}  # Limiter à 2000 caractères pour éviter les prompts trop longs
"""
        
        reponse_str = call_gemini_api(prompt_domaine)
        if not reponse_str:
            return None
            
        # Extraire le JSON de la réponse
        json_match = re.search(r'\{.*\}', reponse_str, re.DOTALL)
        if not json_match:
            return None
            
        donnees = json.loads(json_match.group(0))
        domaine_identifie = donnees.get('domaine')
        
        # Vérifier que le domaine existe dans la base
        if domaine_identifie and domaine_identifie != "AUCUN":
            try:
                domaine_obj = Domaine.objects.get(libelle__iexact=domaine_identifie)
                return domaine_obj
            except Domaine.DoesNotExist:
                pass
                
        return None
        
    except Exception as e:
        print(f"Erreur lors de l'extraction du domaine: {e}")
        return None

def generer_notifications_marche(marche: Marche, domaine: Domaine = None):
    """
    Génère les notifications pour un marché donné.
    - Notifications par domaine pour toutes les entreprises du domaine
    - Notifications spécifiques pour les entreprises mentionnées dans les lots
    """
    notifications_creees = 0
    
    try:
        # 1. Notifications par domaine
        if domaine:
            entreprises_domaine = Entreprise.objects.filter(domaines=domaine)
            for entreprise in entreprises_domaine:
                # Éviter les doublons avec get_or_create
                notification, created = Notification.objects.get_or_create(
                    type_notification='DOMAINE',
                    entreprise=entreprise,
                    marche=marche,
                    domaine=domaine,
                    defaults={
                        'lu': False,
                        'message': f"Nouveau marché dans votre domaine '{domaine.libelle}': {marche.objet}"
                    }
                )
                if created:
                    notifications_creees += 1
        
        # 2. Notifications spécifiques pour les entreprises mentionnées dans les lots
        lots_avec_entreprises = Lot.objects.filter(marche=marche, entreprise_concernee__isnull=False)
        for lot in lots_avec_entreprises:
            notification, created = Notification.objects.get_or_create(
                type_notification='ENTREPRISE_SPECIFIQUE',
                entreprise=lot.entreprise_concernee,
                marche=marche,
                lot=lot,
                defaults={
                    'lu': False,
                    'message': f"Votre entreprise est mentionnée dans le lot {lot.numero_lot}: {lot.description}"
                }
            )
            if created:
                notifications_creees += 1
                
        print(f"Notifications créées pour le marché {marche.id}: {notifications_creees}")
        return notifications_creees
        
    except Exception as e:
        print(f"Erreur lors de la génération des notifications: {e}")
        return 0

@transaction.atomic
def sauvegarder_donnees_notice(data: dict, publication: Publication):
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
    
    domaine_identifie = None
    if marche.objet:  # Si on a un objet de marché
        domaine_identifie = extraire_domaine_avec_ia(marche.objet)
        if domaine_identifie:
            marche.domaine = domaine_identifie
            marche.save()
    
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
    
    generer_notifications_marche(marche, domaine_identifie)

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

        notices_candidates = segmenter_document_en_notices(texte_complet)
        
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
                    sauvegarder_donnees_notice(donnees, publication)
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
