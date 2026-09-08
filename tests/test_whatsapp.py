"""Tests de api/whatsapp_client.py (appel HTTP mocke) et llm_service/whatsapp_prompts.py (LLM
mocke) - aucune dependance a un vrai compte Meta ni a un serveur Ollama reel."""

import json
from types import SimpleNamespace

import pytest

from api.whatsapp_client import WhatsAppSendError, normalize_e164, send_whatsapp_template
from llm_service.traduction_prompts import TraductionEchouee, traduire_texte
from llm_service.whatsapp_prompts import RedactionEchouee, resumer_objet


def _fake_ollama_client(*reponses: str):
    it = iter(reponses)

    class FakeClient:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content=next(it)))

    return FakeClient()


# --- normalize_e164 -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entree,attendu",
    [
        ("70 12 34 56", "+22670123456"),
        ("+226 70 12 34 56", "+22670123456"),
        ("0022670123456", "+22670123456"),
        ("22670123456", "+22670123456"),
    ],
)
def test_normalize_e164(entree, attendu):
    assert normalize_e164(entree) == attendu


# --- send_whatsapp_template ----------------------------------------------------------------------


def test_send_whatsapp_template_succes(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"messages": [{"id": "wamid.test"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("api.whatsapp_client.requests.post", fake_post)

    result = send_whatsapp_template("70123456", parameters=["Ma Boite", "Resume court", "SONATUR"])

    assert result == {"messages": [{"id": "wamid.test"}]}
    assert captured["json"]["to"] == "+22670123456"
    assert captured["json"]["type"] == "template"
    params = captured["json"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["Ma Boite", "Resume court", "SONATUR"]


def test_send_whatsapp_template_erreur_api(monkeypatch):
    class FakeResponse:
        status_code = 400
        text = '{"error": {"message": "Template non approuve"}}'

    monkeypatch.setattr("api.whatsapp_client.requests.post", lambda *a, **k: FakeResponse())

    with pytest.raises(WhatsAppSendError):
        send_whatsapp_template("70123456", parameters=["X", "Y", "Z"])


# --- resumer_objet ---------------------------------------------------------------------------


def test_resumer_objet_reponse_valide(monkeypatch):
    fake_client = _fake_ollama_client(json.dumps({"resume": "Acquisition de logiciels pour la SONATUR"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    resume = resumer_objet("Demande de prix pour l'acquisition de logiciels ArchiCAD, QGIS et MS PROJECT")

    assert resume == "Acquisition de logiciels pour la SONATUR"


def test_resumer_objet_retente_puis_reussit(monkeypatch):
    fake_client = _fake_ollama_client("pas du JSON", json.dumps({"resume": "Resume corrige"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert resumer_objet("texte") == "Resume corrige"


def test_resumer_objet_echoue_apres_deux_tentatives(monkeypatch):
    fake_client = _fake_ollama_client("pas du JSON", "toujours pas du JSON")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    with pytest.raises(RedactionEchouee):
        resumer_objet("texte")


def test_resumer_objet_tronque_a_300_caracteres_au_dernier_mot_complet(monkeypatch):
    # Coupe au dernier espace avant 300 caracteres (jamais en plein milieu d'un mot, cf.
    # _troncature_mot) - contrairement a un simple texte[:300], qui produirait un mot tronque
    # illisible dans le message WhatsApp final. 300 (pas 100) : la limite reelle du gabarit
    # WhatsApp, cf. SYSTEM_PROMPT - un ecart entre les deux avait deja ete constate en reel (le
    # prompt annoncait 300 au LLM pendant que _valider_resume tronquait encore a 100).
    long_resume = "Lorem ipsum dolor sit amet " * 12  # 336 caracteres, plein d'espaces
    fake_client = _fake_ollama_client(json.dumps({"resume": long_resume}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    resume = resumer_objet("texte")

    assert len(resume) <= 303
    assert resume.endswith("...")
    # Le texte tronque doit etre un prefixe MOT POUR MOT du texte original - jamais un mot coupe.
    mots_resultat = resume[:-3].split()
    mots_originaux = long_resume.split()
    assert mots_resultat == mots_originaux[: len(mots_resultat)]


def test_resumer_objet_tronque_sans_espace_ne_depasse_pas_beaucoup(monkeypatch):
    # Cas limite (aucun espace du tout) : pas de mot a preserver, simple coupe dure.
    long_resume = "a" * 350
    fake_client = _fake_ollama_client(json.dumps({"resume": long_resume}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert len(resumer_objet("texte")) <= 303


# --- resumer_objet(langue=...) : selection du prompt systeme par langue ------------------------


def test_resumer_objet_langue_en_reussit_comme_le_francais(monkeypatch):
    # Le LLM est mocke ici (repond deja en anglais dans le JSON) : ce test verifie juste que le
    # parametre `langue` est accepte et que le pipeline de validation/troncature fonctionne a
    # l'identique, pas la qualite reelle de la traduction (verifiee manuellement/en reel).
    fake_client = _fake_ollama_client(json.dumps({"resume": "Software acquisition for SONATUR"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    resume = resumer_objet("Request for quotation for ArchiCAD, QGIS software", langue="en")

    assert resume == "Software acquisition for SONATUR"


def test_resumer_objet_langue_mos_reussit_comme_le_francais(monkeypatch):
    fake_client = _fake_ollama_client(json.dumps({"resume": "Logisiel ragb-buud sɩɩb SONATUR yĩnga"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    resume = resumer_objet("texte", langue="mos")

    assert resume == "Logisiel ragb-buud sɩɩb SONATUR yĩnga"


def test_resumer_objet_langue_inconnue_retombe_sur_le_comportement_par_defaut(monkeypatch):
    # Une langue absente de _SYSTEM_PROMPTS_PAR_LANGUE ne doit jamais faire planter l'appel - repli
    # sur SYSTEM_PROMPT (francais), cf. docstring de resumer_objet.
    fake_client = _fake_ollama_client(json.dumps({"resume": "Resume par defaut"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert resumer_objet("texte", langue="xx") == "Resume par defaut"


# --- traduire_texte -----------------------------------------------------------------------------


def test_traduire_texte_langue_cible_fr_ne_fait_aucun_appel_llm(monkeypatch):
    # Court-circuit documente : le texte source est deja en francais, un aller-retour LLM serait
    # inutile - un client qui leve une exception s'il est sollicite prouve qu'il n'est jamais
    # appele dans ce cas.
    def client_qui_ne_doit_jamais_etre_appele():
        raise AssertionError("call_llm ne doit pas etre appele quand langue_cible == 'fr'")

    monkeypatch.setattr("llm_service.llm_client._get_default_client", client_qui_ne_doit_jamais_etre_appele)

    assert traduire_texte("Texte deja en francais", "fr") == "Texte deja en francais"


def test_traduire_texte_reponse_valide(monkeypatch):
    fake_client = _fake_ollama_client("Public tender notice for computer equipment")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    resultat = traduire_texte("Avis de marche pour du materiel informatique", "en")

    assert resultat == "Public tender notice for computer equipment"


def test_traduire_texte_retente_une_fois_sur_reponse_vide(monkeypatch):
    fake_client = _fake_ollama_client("", "Traduction obtenue apres retry")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert traduire_texte("texte", "en") == "Traduction obtenue apres retry"


def test_traduire_texte_echoue_apres_deux_reponses_vides(monkeypatch):
    fake_client = _fake_ollama_client("", "   ")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    with pytest.raises(TraductionEchouee):
        traduire_texte("texte", "en")
