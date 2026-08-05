"""Tests de llm_service.extraction_prompts (LLM mocke, aucune dependance a un serveur Ollama
reel) et des fonctions pures de api/scripts/extract_bulletin.py (pas de DB necessaire)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from api.scripts.extract_bulletin import (
    _corriger_type_avis,
    _group_by_section,
    _parse_date_bulletin,
    _semble_ligne_de_tableau,
)
from llm_service.extraction_prompts import AvisExtrait, ExtractionEchouee, extraire_avis, parse_llm_date


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


def _avis_minimal(type_avis: str) -> AvisExtrait:
    return AvisExtrait(type_avis=type_avis, organisme="X", objet="Y")


def test_corriger_type_avis_ecrase_llm_si_marqueur_resultat_non_ambigu():
    """Bug reel constate sur le bulletin n°4458 : le LLM classait 'appel_offre' une section qui
    contenait litteralement 'a ete declaree attributaire du marche'."""
    avis = _avis_minimal("appel_offre")
    texte = "L'entreprise « FZ SERVICES SARL » a été déclarée attributaire du marché."

    corrige = _corriger_type_avis(avis, texte, "section test")

    assert corrige.type_avis == "resultat"


def test_corriger_type_avis_ecrase_llm_si_marqueur_appel_offre_non_ambigu():
    avis = _avis_minimal("resultat")
    texte = "Avis d'appel d'offres ouvert (AAOO) n°2026-042 relatif a..."

    corrige = _corriger_type_avis(avis, texte, "section test")

    assert corrige.type_avis == "appel_offre"


def test_corriger_type_avis_garde_llm_si_texte_ambigu():
    """Une page qui enchaine la fin d'un tableau de resultats et un nouvel avis (frequent dans ce
    bulletin) contient les deux familles de marqueurs - on fait alors confiance au LLM plutot que
    de trancher au hasard."""
    avis = _avis_minimal("appel_offre")
    texte = "Non Conforme / Ecartee du classement. Avis d'appel d'offres ouvert (AAOO) n°2026-042."

    corrige = _corriger_type_avis(avis, texte, "section test")

    assert corrige.type_avis == "appel_offre"


def test_corriger_type_avis_garde_llm_si_aucun_marqueur():
    avis = _avis_minimal("autre")
    texte = "Texte quelconque sans marqueur administratif reconnaissable."

    corrige = _corriger_type_avis(avis, texte, "section test")

    assert corrige.type_avis == "autre"
