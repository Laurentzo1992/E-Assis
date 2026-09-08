"""Tests de llm_service/matching_prompts.py (LLM mocke) - aucune dependance a un serveur Ollama
reel."""

import json
from types import SimpleNamespace

import pytest

from llm_service.matching_prompts import VerificationEchouee, verifier_pertinence


def _fake_ollama_client(*reponses: str):
    it = iter(reponses)

    class FakeClient:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content=next(it)))

    return FakeClient()


def test_verifier_pertinence_reponse_valide_pertinent(monkeypatch):
    fake_client = _fake_ollama_client(json.dumps({"pertinent": True, "raison": "Meme domaine"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert verifier_pertinence(["Informatique"], "Fourniture de materiel informatique") is True


def test_verifier_pertinence_reponse_valide_non_pertinent(monkeypatch):
    fake_client = _fake_ollama_client(json.dumps({"pertinent": False, "raison": "Tableau d'attribution, pas un appel"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert verifier_pertinence(["Informatique"], "Resultats d'evaluation de scanners") is False


def test_verifier_pertinence_retente_puis_reussit(monkeypatch):
    fake_client = _fake_ollama_client("pas du JSON", json.dumps({"pertinent": True, "raison": "ok"}))
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    assert verifier_pertinence(["BTP"], "Travaux de voirie") is True


def test_verifier_pertinence_echoue_apres_deux_tentatives(monkeypatch):
    fake_client = _fake_ollama_client("pas du JSON", "toujours pas du JSON")
    monkeypatch.setattr("llm_service.llm_client._get_default_client", lambda: fake_client)

    with pytest.raises(VerificationEchouee):
        verifier_pertinence(["BTP"], "Travaux de voirie")
