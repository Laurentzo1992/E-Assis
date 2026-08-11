"""Tests de llm_service/llm_client.py - aucun serveur Ollama reel requis (client mocke).

Regression pour un incident reel : sans timeout sur ollama.Client(), une requete bloquee
(constate sur le bulletin 4462, section "COMMUNE DE KOUNDOUGOU") gelait l'extraction pendant
plus de 3h sans jamais lever d'erreur, jusqu'a ce qu'Airflow tue la tache comme "zombie"."""

from types import SimpleNamespace

import httpx
import ollama
import pytest

from llm_service.llm_client import (
    OLLAMA_TIMEOUT_S,
    _est_erreur_transitoire,
    _get_default_client,
    call_llm,
)
import llm_service.llm_client as llm_client_module


@pytest.fixture(autouse=True)
def _pas_de_vraie_pause(monkeypatch):
    # Le backoff entre tentatives (jusqu'a MAX_DELAY_S=20s) n'a aucune valeur dans un test.
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda *_: None)


@pytest.fixture(autouse=True)
def _reset_client_singleton():
    llm_client_module._client_singleton = None
    yield
    llm_client_module._client_singleton = None


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


def test_call_llm_retente_apres_un_timeout_puis_reussit():
    appels = {"n": 0}

    class FakeClient:
        def chat(self, **kwargs):
            appels["n"] += 1
            if appels["n"] == 1:
                raise httpx.ReadTimeout("delai depasse")
            return SimpleNamespace(message=SimpleNamespace(content="ok"))

    response = call_llm("extraction", [{"role": "user", "content": "test"}], client=FakeClient())

    assert appels["n"] == 2
    assert response.message.content == "ok"


def test_call_llm_epuise_les_tentatives_si_timeout_persistant():
    class FakeClient:
        def chat(self, **kwargs):
            raise httpx.ReadTimeout("delai depasse")

    with pytest.raises(httpx.ReadTimeout):
        call_llm("extraction", [{"role": "user", "content": "test"}], client=FakeClient())
