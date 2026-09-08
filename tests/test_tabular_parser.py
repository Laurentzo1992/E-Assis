"""Tests unitaires pour le parser tabulaire déterministe et hybride (Étape 4).

Valide :
- La détection de section résultat vs autre section
- L'extraction déterministe d'en-tête (organisme, référence dossier, objet, date)
- L'extraction de lignes de tableaux réels (attributaires, écartés, montants en FCFA)
- Le multi-lots
- La priorité au déterminisme (Règle d'Or n°1).
"""

from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch

from api.services.tabular_resultats_parser import (
    TabularResultatsParser,
    _nettoyer_montant,
)
from llm_service.extraction_resultats_prompts import (
    LotExtractionSchema,
    ResultatExtractionSchema,
    SoumissionnaireExtractionSchema,
)


def test_nettoyage_montant():
    assert _nettoyer_montant("24 500 000 FCFA") == Decimal("24500000.00")
    assert _nettoyer_montant("12.500.000 F CFA") == Decimal("12500000.00")
    assert _nettoyer_montant("5 250 500,50") == Decimal("5250500.50")
    assert _nettoyer_montant("-") is None
    assert _nettoyer_montant("") is None


def test_detection_section_resultat():
    texte_resultat = """
    MINISTERE DE LA SANTE ET DE L'HYGIENE PUBLIQUE
    RESULTATS DU DEPOUILLEMENT DE LA DEMANDE DE PRIX N°2024-012/MSHP
    Objet : Acquisition de réactifs de laboratoire
    """
    assert TabularResultatsParser.est_section_resultat(texte_resultat) is True

    texte_appel = """
    AVIS D'APPEL D'OFFRES OUVERT INTERNATIONAL
    N°2024-001/SONABEL/DG
    Fourniture de compteurs électriques
    """
    assert TabularResultatsParser.est_section_resultat(texte_appel) is False


def test_extraction_en_tete():
    texte = """
    MINISTERE DE L'ENSEIGNEMENT SUPERIEUR, DE LA RECHERCHE ET DE L'INNOVATION
    RESULTATS DE LA DEMANDE DE PRIX N°2024-001/MESRI/SG/DMP
    Objet : Acquisition de fournitures de bureau et consommables informatiques
    Financement : Budget de l'Etat, gestion 2024
    Ouagadougou, le 12 mars 2024
    """
    en_tete = TabularResultatsParser.extraire_en_tete(texte)
    assert "ENSEIGNEMENT SUPERIEUR" in en_tete["autorite_contractante"]
    assert en_tete["reference_dossier"] == "2024-001/MESRI/SG/DMP"
    assert "fournitures de bureau" in en_tete["objet"].lower()
    assert en_tete["date_attribution"] == date(2024, 3, 12)
    assert en_tete["statut_deliberation"] == "ATTRIBUE"


def test_extraction_deterministe_tableau_complet():
    texte_complet = """
    MINISTERE DE LA TRANSITION DIGITALE
    RESULTATS DE LA DEMANDE DE PRIX N°2024-005/MTDPCE
    Objet : Acquisition de matériel informatique et scanners

    Lot 1 : Ordinateurs de bureau
    N° | Soumissionnaires | Montant lu (TTC) | Observation
    1 | FZ SERVICES SARL | 24 500 000 FCFA | Retenu (Attributaire)
    2 | ETS WEND-PANGA | 26 000 000 FCFA | Conforme non retenu
    3 | BURKINA TECH SA | 22 000 000 FCFA | Écarté pour offre technique non conforme

    Lot 2 : Scanners de production
    N° | Soumissionnaires | Montant lu (TTC) | Observation
    1 | SAHAM SERVICES | 15 000 000 FCFA | Attributaire
    """

    res = TabularResultatsParser.parser_texte_resultat(texte_complet)
    assert res is not None
    assert res.methode_extraction == "DETERMINISTE"
    assert len(res.lots) == 2

    lot1 = res.lots[0]
    assert lot1.numero_lot == "1"
    assert len(lot1.soumissionnaires) == 3

    # Vainqueur Lot 1
    gagnant_l1 = lot1.soumissionnaires[0]
    assert gagnant_l1.nom_entreprise_brut == "FZ SERVICES SARL"
    assert gagnant_l1.nom_entreprise_normalise == "fz services"
    assert gagnant_l1.est_attributaire is True
    assert gagnant_l1.statut == "ATTRIBUTAIRE"
    assert gagnant_l1.montant_lu == Decimal("24500000.00")

    # Écarté Lot 1
    ecarte_l1 = lot1.soumissionnaires[2]
    assert ecarte_l1.nom_entreprise_brut == "BURKINA TECH SA"
    assert ecarte_l1.est_attributaire is False
    assert ecarte_l1.statut == "ECARTE"
    assert "technique" in ecarte_l1.motif_rejet.lower()

    # Vainqueur Lot 2
    lot2 = res.lots[1]
    assert lot2.numero_lot == "2"
    assert len(lot2.soumissionnaires) == 1
    assert lot2.soumissionnaires[0].est_attributaire is True


def test_extraction_hybride_avec_fallback_llm():
    texte_non_structure = """
    PROCES-VERBAL D'ATTRIBUTION DU MARCHE N°2024-99
    Autorité contractante : COMMUNE DE KOUDOUGOU
    Objet : Travaux d'aménagement de voiries urbaines
    Par délibération du 15 mai 2024, après examen des offres, l'entreprise BTP PLUS SUARL a été retenue pour un montant total de 85 000 000 FCFA. L'entreprise FASO ROUTE a été écartée pour non-respect des critères administratifs.
    """

    # Mock du retour LLM pour simuler le fallback ciblé
    fake_llm_schema = ResultatExtractionSchema(
        autorite_contractante="COMMUNE DE KOUDOUGOU",
        reference_dossier="2024-99",
        objet="Travaux d'aménagement de voiries urbaines",
        date_attribution="2024-05-15",
        statut_deliberation="ATTRIBUE",
        lots=[
            LotExtractionSchema(
                numero_lot="1",
                intitule_lot="Voiries",
                statut_lot="ATTRIBUE",
                soumissionnaires=[
                    SoumissionnaireExtractionSchema(
                        nom_entreprise="BTP PLUS SUARL",
                        est_attributaire=True,
                        statut="ATTRIBUTAIRE",
                        montant_lu=85000000.0,
                        montant_corrige=85000000.0,
                    ),
                    SoumissionnaireExtractionSchema(
                        nom_entreprise="FASO ROUTE",
                        est_attributaire=False,
                        statut="ECARTE",
                        motif_rejet="Non-respect des critères administratifs",
                    ),
                ],
            )
        ],
    )

    with patch("api.services.tabular_resultats_parser.extraire_resultats_avec_llm", return_value=fake_llm_schema):
        res = TabularResultatsParser.extraire_resultat_hybride(texte_non_structure)
        assert res is not None
        assert res.methode_extraction == "LLM_FALLBACK"
        assert res.reference_dossier == "2024-99"
        assert len(res.lots) == 1
        assert len(res.lots[0].soumissionnaires) == 2
        assert res.lots[0].soumissionnaires[0].est_attributaire is True
        assert res.lots[0].soumissionnaires[0].nom_entreprise_normalise == "btp plus"
