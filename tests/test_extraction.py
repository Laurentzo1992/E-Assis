"""Tests de llm_service.extraction_prompts (LLM mocke, aucune dependance a un serveur Ollama
reel) et des fonctions pures de api/scripts/extract_bulletin.py (pas de DB necessaire)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from api.scripts.extract_bulletin import (
    _detecter_type_avis,
    _group_by_section,
    _parse_date_bulletin,
    _semble_ligne_de_tableau,
    _semble_repertoire_fournisseurs,
    _semble_trop_courte,
)
from llm_service.extraction_prompts import (
    ExtractionEchouee,
    extraire_appel_offre,
    extraire_avis,
    extraire_resultat,
    parse_llm_date,
)


def _fake_ollama_client(*reponses: str):
    """Un client Ollama factice dont .chat() renvoie successivement chaque reponse fournie."""
    it = iter(reponses)

    class FakeClient:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content=next(it)))

    return FakeClient()


def test_extraire_avis_liste_vide_si_pas_un_avis(monkeypatch):
    fake_client = _fake_ollama_client("[]")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)
    result = extraire_avis("N°3827 - lundi 04 Mars 2024 - 1 - www.dgcmef.gov.bf")
    assert result == []


def test_extraire_avis_ignore_les_elements_non_objet(monkeypatch):
    """Constate en reel avec mistral-nemo:12b sur un bulletin dense (181 sections) : le tableau
    contient parfois un element qui est une chaine brute au lieu d'un objet - faisait planter tout
    extract_bulletin() (AttributeError non rattrapee) avant ce correctif."""
    reponse = json.dumps([
        "ceci n'est pas un avis",
        {"type_avis": "autre", "organisme": "X", "objet": "Y", "type_procedure": None,
         "montant_min": None, "montant_max": None, "date_avis": None,
         "entreprise_attributaire_nom": None, "montant_attribue": None},
    ])
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_avis("texte")

    assert len(result) == 1
    assert result[0].organisme == "X"


def test_extraire_avis_liste_vide_si_objet_vide(monkeypatch):
    """Certains modeles (mistral-nemo, qwen2.5 constates en reel) renvoient `{}` au lieu du
    tableau vide `[]` demande par le prompt quand la section ne contient aucun avis."""
    fake_client = _fake_ollama_client("{}")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)
    result = extraire_avis("en-tete de page sans avis")
    assert result == []


def test_extraire_avis_parse_un_appel_offre(monkeypatch):
    reponse = json.dumps([
        {
            "type_avis": "appel_offre",
            "organisme": "SONATUR",
            "objet": "Acquisition de logiciels ArchiCAD, QGIS et MS PROJECT",
            "type_procedure": "demande de prix",
            "montant_min": None,
            "montant_max": 42700000,
            "date_avis": "2026-04-27",
            "entreprise_attributaire_nom": None,
            "montant_attribue": None,
        }
    ])
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_avis("SOCIETE NATIONALE D'AMENAGEMENT... Demande de prix n°2026-006...")

    assert len(result) == 1
    assert result[0].type_avis == "appel_offre"
    assert result[0].organisme == "SONATUR"
    assert result[0].montant_max == 42700000


def test_extraire_avis_retente_une_fois_puis_reussit(monkeypatch):
    reponse_valide = json.dumps([
        {"type_avis": "autre", "organisme": "X", "objet": "Y", "type_procedure": None,
         "montant_min": None, "montant_max": None, "date_avis": None,
         "entreprise_attributaire_nom": None, "montant_attribue": None}
    ])
    fake_client = _fake_ollama_client("ceci n'est pas du JSON", reponse_valide)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_avis("texte quelconque")
    assert len(result) == 1
    assert result[0].type_avis == "autre"


def test_extraire_avis_echoue_apres_deux_reponses_invalides(monkeypatch):
    fake_client = _fake_ollama_client("pas du JSON", "toujours pas du JSON")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    with pytest.raises(ExtractionEchouee):
        extraire_avis("texte quelconque")


def test_group_by_section_regroupe_et_trie_par_page_et_chunk_index():
    chunks = [
        {"page_number": 1, "chunk_index": 1, "section_title": "ORGANISME A", "text": "deuxieme"},
        {"page_number": 1, "chunk_index": 0, "section_title": "ORGANISME A", "text": "premier"},
        {"page_number": 1, "chunk_index": 2, "section_title": "ORGANISME B", "text": "autre avis"},
    ]

    sections = _group_by_section(chunks)

    assert [s.label for s in sections] == ["ORGANISME A", "ORGANISME B"]
    # tri par (page_number, chunk_index) au sein d'une meme section : "premier" (c0) avant "deuxieme" (c1)
    assert sections[0].texte == "premier\n\ndeuxieme"
    assert sections[0].page_number == 1
    assert sections[1].texte == "autre avis"


def test_group_by_section_ne_fusionne_pas_deux_occurrences_non_contigues():
    """Bug reel constate sur le bulletin n°4458 : un dict classique fusionnerait toutes les
    occurrences d'un meme titre (ou tous les chunks sans titre) en un seul groupe, meme separees
    de plusieurs pages sans rapport - cf. docstring de `_group_by_section`."""
    chunks = [
        {"page_number": 1, "chunk_index": 0, "section_title": None, "text": "bloc sans titre 1"},
        {"page_number": 2, "chunk_index": 0, "section_title": "SONABHY", "text": "premier avis SONABHY"},
        {"page_number": 3, "chunk_index": 0, "section_title": None, "text": "bloc sans titre 2"},
        {"page_number": 4, "chunk_index": 0, "section_title": "SONABHY", "text": "second avis SONABHY"},
    ]

    sections = _group_by_section(chunks)

    assert [s.label for s in sections] == ["sans-titre", "SONABHY", "sans-titre #2", "SONABHY #2"]
    assert [s.texte for s in sections] == [
        "bloc sans titre 1", "premier avis SONABHY", "bloc sans titre 2", "second avis SONABHY",
    ]
    assert [s.page_number for s in sections] == [1, 2, 3, 4]


def test_parse_date_bulletin_formats():
    assert _parse_date_bulletin("Vendredi 31 juillet 2026").isoformat() == "2026-07-31"
    assert _parse_date_bulletin("15 mars 2025") is not None
    assert _parse_date_bulletin(None) is None
    assert _parse_date_bulletin("texte sans date") is None


# --- Regression : cas reels observes lors du premier run complet sur le bulletin n°4456 --------


def test_parse_llm_date_formats_reels_observes():
    assert parse_llm_date("2026-07-31") == date(2026, 7, 31)
    assert parse_llm_date("2020").isoformat() == "2020-01-01"
    assert parse_llm_date("Non spécifiée") is None
    assert parse_llm_date("Date non spécifiée") is None
    assert parse_llm_date("20XX-00-00") is None
    assert parse_llm_date("BF-OUA-01-2024-B13-02914") is None
    assert parse_llm_date(None) is None


def test_semble_ligne_de_tableau_detecte_les_lignes_de_classement_reelles():
    for titre in ["89 BEN MOUSTAPHA 7 SERVICES", "249 SCOOPS ALHMARIA", "12 BARAKO TRADING", "5 NOURA SERVICES SARL"]:
        assert _semble_ligne_de_tableau(titre), titre


def test_semble_ligne_de_tableau_laisse_passer_les_vrais_titres():
    for titre in ["SOCIETE NATIONALE D'AMENAGEMENT DES TERRAINS URBAINS (SONATUR)", "MINISTERE DE LA SANTE", None]:
        assert not _semble_ligne_de_tableau(titre), titre


def test_semble_repertoire_fournisseurs_detecte_une_fiche_synthese_reelle():
    """Bug reel constate sur le bulletin n°4459 : une section de "fiche de synthese de la base de
    donnees des fournisseurs" (nom d'entreprise detecte a tort comme titre d'avis par le chunking,
    cf. ingestion/chunking.py) contenant plusieurs lignes IFU a fait halluciner au LLM un avis
    d'appel d'offres complet ("Fourniture de materiel informatique pour les services de la
    primature") ne correspondant a aucun texte reel du bulletin."""
    texte = """FASO EQUIPEMENT PAALGA
OUEDRAOGO ISSAKA
00106336Y
BFOUA2018A4836
76097609/63316161
24
FIRST UNITED GROUP
OUEDRAOGO YACOUBA
00200146A
BFOUA-01-2023-B12-04339
54145900"""
    assert _semble_repertoire_fournisseurs(texte)


def test_semble_repertoire_fournisseurs_detecte_ifu_avec_espace():
    """Constate en reel sur le bulletin n°4460 : l'extraction PDF insere parfois une espace entre
    le numero IFU et sa lettre finale (ex. "00223311 U" au lieu de "00223311U")."""
    texte = """2
SONEVI/MS Sarl
BF- OHG -2023 B 667 00223311 U
Retenu
3
WE SEE INNOV GROUP
BF- OUA-01-2025-B13-18656 00291703 X
Non retenu"""
    assert _semble_repertoire_fournisseurs(texte)


def test_semble_repertoire_fournisseurs_laisse_passer_un_vrai_avis():
    texte = "Demande de prix n°2026-006/SONATUR relative a l'acquisition de logiciels ArchiCAD, QGIS et MS PROJECT."
    assert not _semble_repertoire_fournisseurs(texte)


def test_semble_trop_courte_detecte_un_en_tete_de_page_seul():
    """Bug reel constate sur le bulletin n°4459 : une section reduite au seul en-tete de page
    repete (~64 caracteres, aucun contenu) a quand meme fait halluciner un avis complet au LLM."""
    texte = """N°3827 – lundi 04 Mars 2024

37

N° 4459 – Mercredi 05 Août 2026"""
    assert _semble_trop_courte(texte)


def test_semble_trop_courte_detecte_la_variante_longue_de_l_en_tete():
    """Meme bug, variante plus longue (151 caracteres, avec les URL) constatee sur le bulletin
    n°4460 - le premier seuil de 100 caracteres etait trop bas pour l'exclure."""
    texte = """N°3827 – lundi 04 Mars 2024

59

N° 4460 – Jeudi 06 Août 2026

www.dgcmef.gov.bf                                                    www.finances.gov.bf"""
    assert _semble_trop_courte(texte)


def test_semble_trop_courte_laisse_passer_un_vrai_avis():
    """Texte representatif d'un vrai avis reel (organisme + objet + reference + financement,
    cf. bulletin n°4459 page 76) - toujours largement au-dessus du seuil en conditions reelles."""
    texte = (
        "MINISTERE DE L'AGRICULTURE, DE L'EAU, DES RESSOURCES ANIMALES ET HALIEUTIQUES\n\n"
        "Acquisition de materiel et outillage techniques au profit de la Direction Generale "
        "de l'Environnement et du Cadre de Vie (DGECV)\n\n"
        "Avis de demande de prix\n"
        "N°2026-13f/MAERAH/SG/DMP\n"
        "Financement : Budget de l'Etat, Exercice 2026\n"
        "Montant previsionnel : Cinquante-cinq millions quatre-vingt-quatre mille sept cent."
    )
    assert not _semble_trop_courte(texte)


def test_semble_repertoire_fournisseurs_laisse_passer_un_tableau_evaluation_technique():
    """Non-regression : un tableau d'evaluation technique/prix (sans colonne IFU) a deja permis
    d'extraire avec succes le resultat FZ SERVICES SARL sur le bulletin n°4458 (montant exact
    retrouve) - ce type de tableau ne doit jamais etre filtre avant l'appel LLM, meme s'il repete
    "Non Conforme" plusieurs fois."""
    texte = """GRACIERA SERVICES
35 475 000
Non Conforme
ESOFT BURKINA
34 701 440
Non Conforme
Attributaire : L'entreprise « FZ SERVICES SARL » a ete declaree attributaire du marche."""
    assert not _semble_repertoire_fournisseurs(texte)


@pytest.mark.parametrize(
    "enveloppe",
    ["avis_1", "avises", "appel_offre", "avis_marche", "n_importe_quelle_cle"],
)
def test_extraire_avis_deballe_n_importe_quelle_cle_enveloppante(monkeypatch, enveloppe):
    """format='json' (mode JSON natif d'Ollama) pousse parfois le modele a envelopper la liste
    sous une cle arbitraire au lieu du tableau nu demande - constate en reel sur le bulletin
    n°4456 avec des cles differentes a chaque fois ('avis_1', 'avises', 'appel_offre'...)."""
    reponse = json.dumps({
        enveloppe: [
            {"type_avis": "autre", "organisme": "X", "objet": "Y", "type_procedure": None,
             "montant_min": None, "montant_max": None, "date_avis": None,
             "entreprise_attributaire_nom": None, "montant_attribue": None}
        ]
    })
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_avis("texte")

    assert len(result) == 1
    assert result[0].organisme == "X"


def test_extraire_avis_deballe_un_objet_unique_enveloppe(monkeypatch):
    reponse = json.dumps({
        "avis_1": {"type_avis": "autre", "organisme": "X", "objet": "Y", "type_procedure": None,
                   "montant_min": None, "montant_max": None, "date_avis": None,
                   "entreprise_attributaire_nom": None, "montant_attribue": None}
    })
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_avis("texte")

    assert len(result) == 1


def test_extraire_avis_normalise_les_synonymes_de_type_avis(monkeypatch):
    reponse = json.dumps([
        {"type_avis": "retenu", "organisme": "X", "objet": "Y", "type_procedure": None,
         "montant_min": None, "montant_max": None, "date_avis": None,
         "entreprise_attributaire_nom": "Z", "montant_attribue": 1000}
    ])
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_avis("texte")

    assert result[0].type_avis == "resultat"


def test_detecter_type_avis_marqueur_resultat_non_ambigu():
    """Bug reel constate sur le bulletin n°4458 : le LLM (avec l'ancien prompt generique unique)
    classait a tort 'appel_offre' une section qui contenait litteralement 'a ete declaree
    attributaire du marche' - desormais le type est tranche AVANT tout appel LLM, evitant meme
    de poser la question a un modele faillible."""
    texte = "L'entreprise « FZ SERVICES SARL » a été déclarée attributaire du marché."
    assert _detecter_type_avis(texte) == "resultat"


def test_detecter_type_avis_marqueur_appel_offre_non_ambigu():
    texte = "Avis d'appel d'offres ouvert (AAOO) n°2026-042 relatif a..."
    assert _detecter_type_avis(texte) == "appel_offre"


def test_detecter_type_avis_none_si_texte_ambigu():
    """Une page qui enchaine la fin d'un tableau de resultats et un nouvel avis (frequent dans ce
    bulletin) contient les deux familles de marqueurs - retourne None (repli sur le prompt
    generique, ou le LLM classifie lui-meme) plutot que de trancher au hasard."""
    texte = "Non Conforme / Ecartee du classement. Avis d'appel d'offres ouvert (AAOO) n°2026-042."
    assert _detecter_type_avis(texte) is None


def test_detecter_type_avis_none_si_aucun_marqueur():
    texte = "Texte quelconque sans marqueur administratif reconnaissable."
    assert _detecter_type_avis(texte) is None


def test_detecter_type_avis_resultat_meme_si_resultat_cite_sa_demande_de_prix():
    """Bug reel constate lors de l'audit du 09/08/2026 (bulletins 4457-4461, ~15 marches affectes) :
    un resultat de "demande de prix" cite systematiquement en en-tete "Demande de prix n°XXX du
    DATE pour <objet>" pour rappeler de quel appel il presente le resultat - un gabarit identique a
    celui d'un nouvel appel. Avant retrait de ce marqueur trop generique de _MARQUEURS_APPEL_OFFRE,
    cette citation neutralisait a tort le marqueur resultat pourtant present ('Non conforme'),
    rendant la section 'ambigue' et laissant un LLM faillible trancher seul."""
    texte = (
        "Demande de prix n°2026-016/MEBAPLN/SG/DMP du 15/06/2026 pour l'entretien et la maintenance "
        "des installations solaires, du circuit electrique, de la plomberie et des appareils "
        "sanitaires au profit du BCMP, de la DGESS, et du SP-PSDEBS (marche a commandes)\n"
        "SAID MULTI-SERVICES 8 237 750 15 439 750 - - - - - - Non conforme "
        "Absence des items 90, 91, 92, 93 et 94"
    )
    assert _detecter_type_avis(texte) == "resultat"


def test_detecter_type_avis_resultat_si_attributaire_seul_sans_qualificatif():
    """Bug reel constate sur le bulletin n°4461 (marche SONATUR n°2026-004/DG-SONATUR/PRM) : le
    LLM classait a tort 'appel_offre' une section de resultat ou 'Attributaire' apparait seul,
    comme etiquette de tableau suivie du nom du gagnant, sans le qualificatif 'provisoire'/
    'definitif' que l'ancien marqueur exigeait - laissant ainsi un marche deja attribue rejoindre
    le pool des appels d'offres ouverts et generer de fausses alertes 'nouvelle opportunite'."""
    texte = (
        "Reference de publication de resultats de l'AMI : RMP n°4407 du 25/05/2026 (page 13)\n"
        "Date de deliberation : 24 juillet 2026\n"
        "Attributaire\n"
        "IKA SOLUTION LTD pour un montant de vingt-deux millions quatre cent vingt mille "
        "(22 420 000) francs CFA TTC avec un delai d'execution de quatre-vingt-dix (90) jours"
    )
    assert _detecter_type_avis(texte) == "resultat"


# --- extraire_resultat / extraire_appel_offre (prompts specialises, type deja connu) -----------


def test_extraire_resultat_impose_le_type_sans_le_demander_au_llm(monkeypatch):
    # Le prompt RESULTAT ne demande plus "type_avis" au LLM (deja connu) - _valider_avis_resultat
    # doit l'imposer lui-meme independamment de ce que contient (ou non) la reponse.
    reponse = json.dumps([
        {"organisme": "CARFO", "objet": "Entretien de groupes electrogenes", "type_procedure": None,
         "montant_min": None, "montant_max": None, "date_avis": None,
         "entreprise_attributaire_nom": "FZ SERVICES SARL", "montant_attribue": 12000000}
    ])
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_resultat("texte de resultat")

    assert len(result) == 1
    assert result[0].type_avis == "resultat"
    assert result[0].entreprise_attributaire_nom == "FZ SERVICES SARL"


def test_extraire_appel_offre_impose_le_type_sans_le_demander_au_llm(monkeypatch):
    reponse = json.dumps([
        {"organisme": "SONATUR", "objet": "Acquisition de logiciels", "type_procedure": "demande de prix",
         "montant_min": None, "montant_max": 42700000, "date_avis": "2026-04-27"}
    ])
    fake_client = _fake_ollama_client(reponse)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_appel_offre("texte d'appel d'offres")

    assert len(result) == 1
    assert result[0].type_avis == "appel_offre"
    assert result[0].organisme == "SONATUR"


def test_extraire_appel_offre_liste_vide_si_pas_un_avis(monkeypatch):
    fake_client = _fake_ollama_client("[]")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)
    assert extraire_appel_offre("texte") == []


def test_extraire_resultat_retente_puis_reussit(monkeypatch):
    reponse_valide = json.dumps([
        {"organisme": "X", "objet": "Y", "type_procedure": None, "montant_min": None,
         "montant_max": None, "date_avis": None, "entreprise_attributaire_nom": None,
         "montant_attribue": None}
    ])
    fake_client = _fake_ollama_client("ceci n'est pas du JSON", reponse_valide)
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    result = extraire_resultat("texte quelconque")

    assert len(result) == 1
    assert result[0].type_avis == "resultat"
