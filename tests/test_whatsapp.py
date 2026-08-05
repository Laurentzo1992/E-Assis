"""Tests de api/whatsapp_client.py (appel HTTP mocke) et llm_service/whatsapp_prompts.py (LLM
mocke) - aucune dependance a un vrai compte Meta ni a un serveur Ollama reel."""

import json
from types import SimpleNamespace

import pytest

from api.whatsapp_client import WhatsAppSendError, normalize_e164, send_whatsapp_template
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


def test_resumer_objet_tronque_a_100_caracteres(monkeypatch):
    long_resume = "a" * 150
    fake_client = _fake_ollama_client(json.dumps({"resume": long_resume}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert len(resumer_objet("texte")) == 100
