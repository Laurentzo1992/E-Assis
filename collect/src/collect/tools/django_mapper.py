from entreprise.models import Entreprise, Domaine, SecteurActivite
from backend.models import (
    Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot, Alerte, PublicationDomaine
)
from django.utils import timezone

def save_extracted_data(data):
    """
    Save structured data extracted from a PDF page into the database.
    Expects a dictionary with keys matching the CrewAI output format.
    """
    # --- 1. Entreprise ---
    entreprise_data = data.get("entreprise")
    if entreprise_data:
        entreprise, _ = Entreprise.objects.get_or_create(
            nom=entreprise_data.get("nom"),
            defaults={
                "numero_identification": entreprise_data.get("numero_identification", ""),
                "siret": entreprise_data.get("siret", ""),
                "adresse": entreprise_data.get("adresse", ""),
                "telephone": entreprise_data.get("telephone", ""),
                "email": entreprise_data.get("email", ""),
                "date_creation": entreprise_data.get("date_creation"),
                "description": entreprise_data.get("description", ""),
                "repnom": entreprise_data.get("repnom", ""),
                "repprenom": entreprise_data.get("repprenom", ""),
                "rccm": entreprise_data.get("rccm", ""),
            }
        )
        # ManyToMany: domaines
        for domaine_nom in entreprise_data.get("domaines", []):
            domaine, _ = Domaine.objects.get_or_create(libelle=domaine_nom)
            entreprise.domaines.add(domaine)
        # ManyToMany: secteurs
        for secteur_nom in entreprise_data.get("secteurs", []):
            secteur, _ = SecteurActivite.objects.get_or_create(nom=secteur_nom)
            entreprise.secteurs.add(secteur)
    else:
        entreprise = None

    # --- 2. Domaine & TypeProcedure ---
    domaine_obj = None
    if data.get("domaine"):
        domaine_obj, _ = Domaine.objects.get_or_create(libelle=data["domaine"])
    type_proc_obj = None
    if data.get("type_procedure"):
        type_proc_obj, _ = TypeProcedure.objects.get_or_create(libelle=data["type_procedure"])

    # --- 3. Publication ---
    publication_data = data.get("publication", {})
    publication, _ = Publication.objects.get_or_create(
        numero=publication_data.get("numero", ""),
        defaults={
            "titre": publication_data.get("titre", ""),
            "date_publication": publication_data.get("date_publication"),
            "source": publication_data.get("source", ""),
            "source_url": publication_data.get("source_url", ""),
            "type_publication": publication_data.get("type_publication", ""),
        }
    )
    # ManyToMany: domaines
    if domaine_obj:
        PublicationDomaine.objects.get_or_create(publication=publication, domaine=domaine_obj)

    # --- 4. Marche (or AppelOffre) ---
    marche_data = data.get("marche", {})
    marche, _ = Marche.objects.get_or_create(
        publication=publication,
        objet=marche_data.get("objet", ""),
        defaults={
            "type_procedure": type_proc_obj,
            "ministere": marche_data.get("ministere", ""),
            "region": marche_data.get("region", ""),
            "budget_min": marche_data.get("budget_min"),
            "budget_max": marche_data.get("budget_max"),
        }
    )

    # --- 5. Lots ---
    for lot_data in data.get("lots", []):
        Lot.objects.get_or_create(
            marche=marche,
            numero_lot=lot_data.get("numero_lot"),
            defaults={
                "description": lot_data.get("description", ""),
                "montant": lot_data.get("montant"),
            }
        )

    # --- 6. Resultat ---
    resultat_data = data.get("resultat", {})
    if resultat_data:
        Resultat.objects.get_or_create(
            marche=marche,
            defaults={
                "date_attribution": resultat_data.get("date_attribution"),
                "entreprise_attributaire": entreprise,
                "montant_attribue": resultat_data.get("montant_attribue"),
                "reference_decision": resultat_data.get("reference_decision", ""),
                "nombre_offres_recues": resultat_data.get("nombre_offres_recues"),
                "delai_execution": resultat_data.get("delai_execution", ""),
                "motif_rejet_autres_offres": resultat_data.get("motif_rejet_autres_offres", ""),
            }
        )

    # --- 7. Alerte (optional, if you want to create one) ---
    if data.get("alerte"):
        Alerte.objects.create(
            entreprise=entreprise,
            publication=publication,
            type_alerte=data["alerte"].get("type_alerte", ""),
            date_alerte=data["alerte"].get("date_alerte", timezone.now()),
            contenu_alerte=data["alerte"].get("contenu_alerte", ""),
            canal_alerte=data["alerte"].get("canal_alerte", ""),
        )

    return {
        "entreprise": entreprise,
        "publication": publication,
        "marche": marche
    }
