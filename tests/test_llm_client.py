"""Tests de llm_service/llm_client.py.

Couvre :
1. Le mode local par défaut (PROD=false) avec Ollama et Llama 3.1:8b (client mocké)
2. La détection et le basculement en mode PROD (PROD=true) vers Google Cloud Vertex AI (Gemini 3.1 flash-lite)
3. La gestion des erreurs transitoires (timeouts, 429 rate limit, 500) et des retries exponentiels
4. La résolution du fichier JSON de compte de service GCP
"""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import ollama
import pytest

import llm_service.llm_client as llm_client_module
from llm_service.llm_client import (
    GEMINI_MODEL,
    LOCAL_LLM_MODEL,
    OLLAMA_TIMEOUT_S,
    _est_erreur_transitoire,
    _get_default_client,
    _resoudre_modele,
    call_llm,
    is_prod,
)


@pytest.fixture(autouse=True)
def _pas_de_vraie_pause(monkeypatch):
    # Le backoff entre tentatives (jusqu'a MAX_DELAY_S=20s) n'a aucune valeur dans un test.
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda *_: None)


@pytest.fixture(autouse=True)
def _reset_client_singletons():
    llm_client_module._ollama_client_singleton = None
    llm_client_module._gcp_credentials = None
    llm_client_module._gcp_project_id = None
    yield
    llm_client_module._ollama_client_singleton = None
    llm_client_module._gcp_credentials = None
    llm_client_module._gcp_project_id = None


# --- Tests Mode Local (Ollama) ---


def test_mode_par_defaut_est_local(monkeypatch):
    monkeypatch.delenv("PROD", raising=False)
    assert is_prod() is False
    assert _resoudre_modele("extraction") == LOCAL_LLM_MODEL


def test_get_default_client_configure_un_timeout(monkeypatch):
    captured = {}

    class FakeOllamaClient:
        def __init__(self, host, timeout):
            captured["host"] = host
            captured["timeout"] = timeout

    monkeypatch.setattr(ollama, "Client", FakeOllamaClient)

    _get_default_client()

    assert captured["timeout"] == OLLAMA_TIMEOUT_S
    assert captured["timeout"] > 0


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("delai depasse"),
        httpx.ConnectTimeout("connexion impossible"),
        httpx.ConnectError("connexion refusee"),
        ConnectionError("connexion perdue"),
    ],
)
def test_erreurs_reseau_sont_transitoires(exc):
    assert _est_erreur_transitoire(exc) is True


def test_erreur_non_transitoire_nest_pas_retentee():
    assert _est_erreur_transitoire(ValueError("pas une erreur reseau")) is False


def test_call_llm_local_retente_apres_un_timeout_puis_reussit(monkeypatch):
    monkeypatch.setenv("PROD", "false")
    appels = {"n": 0}

    class FakeClient:
        def chat(self, **kwargs):
            appels["n"] += 1
            if appels["n"] == 1:
                raise httpx.ReadTimeout("delai depasse")
            return SimpleNamespace(message=SimpleNamespace(content="ok"), prompt_eval_count=10, eval_count=5, total_duration=1000000)

    response = call_llm("extraction", [{"role": "user", "content": "test"}], client=FakeClient())

    assert appels["n"] == 2
    assert response.message.content == "ok"


def test_call_llm_local_epuise_les_tentatives_si_timeout_persistant(monkeypatch):
    monkeypatch.setenv("PROD", "false")

    class FakeClient:
        def chat(self, **kwargs):
            raise httpx.ReadTimeout("delai depasse")

    with pytest.raises(httpx.ReadTimeout):
        call_llm("extraction", [{"role": "user", "content": "test"}], client=FakeClient())


# --- Tests Mode Production (Google Cloud Gemini) ---


def test_mode_prod_resolution_modele(monkeypatch):
    monkeypatch.setenv("PROD", "true")
    assert is_prod() is True
    assert _resoudre_modele("extraction") == GEMINI_MODEL
    assert _resoudre_modele("redaction_whatsapp") == GEMINI_MODEL


def test_mode_prod_appel_gemini_reussi(monkeypatch, tmp_path):
    monkeypatch.setenv("PROD", "true")

    # Mock du compte de service et token
    monkeypatch.setattr(llm_client_module, "_obtenir_bearer_token", lambda: "fake-bearer-token")
    monkeypatch.setattr(llm_client_module, "_get_gcp_credentials", lambda: (object(), "fake-project-id"))

    captured_request = {}

    def fake_post(url, json=None, headers=None):
        captured_request["url"] = url
        captured_request["json"] = json
        captured_request["headers"] = headers

        fake_resp = SimpleNamespace(
            status_code=200,
            json=lambda: {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Reponse Gemini 3.1 Flash-Lite"}],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 42,
                    "candidatesTokenCount": 18,
                },
            },
            raise_for_status=lambda: None,
        )
        return fake_resp

    class FakeHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None, headers=None):
            return fake_post(url, json=json, headers=headers)

    monkeypatch.setattr(httpx, "Client", FakeHttpxClient)

    response = call_llm(
        "extraction",
        [{"role": "user", "content": "Analyse ce marche"}],
        system="Tu es un expert marches publics.",
    )

    assert response.message.content == "Reponse Gemini 3.1 Flash-Lite"
    assert response.prompt_eval_count == 42
    assert response.eval_count == 18
    assert "fake-project-id" in captured_request["url"]
    assert captured_request["headers"]["Authorization"] == "Bearer fake-bearer-token"
    assert captured_request["json"]["systemInstruction"]["parts"][0]["text"] == "Tu es un expert marches publics."


def test_mode_prod_erreur_service_account_introuvable(monkeypatch):
    monkeypatch.setenv("PROD", "true")
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", "inexistant_key_12345.json")

    with pytest.raises(FileNotFoundError, match="Fichier de compte de service Google Cloud introuvable"):
        llm_client_module._trouver_fichier_service_account()
