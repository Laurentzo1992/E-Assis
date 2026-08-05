"""Wrapper centralise pour tous les appels LLM de kbbot, executes localement via Ollama.

Pattern repris tel quel de fasofoodalert-core/llm_service/llm_client.py (deja en production dans
ce projet voisin, meme choix d'architecture : Ollama auto-heberge plutot qu'une API payante, pour
le cout et la souverainete des donnees des entreprises inscrites).

Tout appel LLM passe par `call_llm()`, qui centralise :
- la selection du modele par tache (`MODELES_PAR_TACHE`) ;
- le retry/backoff exponentiel sur les erreurs transitoires (serveur Ollama injoignable, erreurs
  5xx) - les erreurs non transitoires (modele absent, requete invalide, tache inconnue...) ne sont
  jamais retentees ;
- le logging structure des tokens consommes et de la duree, pour chaque appel reussi.

Modele d'extraction en cours de comparaison reelle sur le bulletin n°4458 (66 sections) :
- mistral:7b (baseline) : 60 marches, 4 corrections de type_avis, 7 reponses JSON invalides, 4
  echecs definitifs.
- mistral-nemo:12b : PIRE que la baseline malgre sa taille superieure - 54 marches, 12 reponses
  JSON invalides, 8 echecs definitifs (renvoie parfois un objet vide `{}` au lieu du tableau vide
  `[]` demande par le prompt en cas d'absence d'avis, ce que `_valider_avis` ne gere pas).
- qwen2.5:14b : en cours d'evaluation.
`mistral:7b` reste utilise pour la redaction du resume WhatsApp (tache courte, une phrase, ou sa
qualite suffit deja). Tous les modeles sont deja presents sur l'hote Ollama (`ollama list`), aucun
telechargement necessaire une fois pulles. Les modeles >7b sont plus lents et plus gourmands en
VRAM, partagee avec vision-ocr (DeepSeek-OCR) sur le meme GPU.
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import ollama
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODELES_PAR_TACHE: dict[str, str] = {
    "extraction": "mistral-nemo:12b",
    "redaction_whatsapp": "mistral:7b",
}

# "ollama" = nom du service dans docker-compose.llm.yml (reseau Docker "backend") ; "localhost"
# suppose un usage depuis l'hote directement.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

DEFAULT_MAX_TOKENS = 4096
MAX_RETRIES = 4
BASE_DELAY_S = 1.0
MAX_DELAY_S = 20.0


@dataclass(frozen=True)
class LLMUsage:
    task: str
    model: str
    input_tokens: int
    output_tokens: int
    duree_ms: float


class TacheInconnue(ValueError):
    """Levee quand `call_llm()` recoit une `task` absente de `MODELES_PAR_TACHE`."""


def _resoudre_modele(task: str) -> str:
    try:
        return MODELES_PAR_TACHE[task]
    except KeyError:
        raise TacheInconnue(f"Tache LLM inconnue : {task!r}. Taches disponibles : {sorted(MODELES_PAR_TACHE)}") from None


def _est_erreur_transitoire(exc: Exception) -> bool:
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, ollama.ResponseError):
        return exc.status_code >= 500
    return False


_client_singleton: ollama.Client | None = None


def _get_default_client() -> ollama.Client:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = ollama.Client(host=OLLAMA_HOST)
    return _client_singleton


def call_llm(
    task: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    system: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: ollama.Client | None = None,
    **kwargs: Any,
) -> Any:
    """Point d'entree unique pour tout appel LLM dans kbbot.

    `client` permet d'injecter un client Ollama (ou un mock dans les tests) - sinon un client
    singleton est construit depuis `OLLAMA_HOST`.
    """
    model = _resoudre_modele(task)
    ollama_client = client if client is not None else _get_default_client()

    full_messages = list(messages)
    if system is not None:
        full_messages = [{"role": "system", "content": system}, *full_messages]

    options = {"num_predict": max_tokens, **kwargs.pop("options", {})}
    chat_kwargs: dict[str, Any] = {
        "model": model,
        "messages": full_messages,
        "options": options,
        **kwargs,
    }

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = ollama_client.chat(**chat_kwargs)
        except Exception as exc:
            last_exc = exc
            if not _est_erreur_transitoire(exc) or attempt == MAX_RETRIES:
                logger.error(
                    "Appel LLM echoue definitivement (tache=%s, modele=%s, tentative=%d/%d) : %s",
                    task, model, attempt, MAX_RETRIES, exc,
                )
                raise
            delay = min(BASE_DELAY_S * (2 ** (attempt - 1)) + random.uniform(0, 1), MAX_DELAY_S)
            logger.warning(
                "Erreur transitoire LLM (tache=%s, modele=%s, tentative=%d/%d) - nouvelle tentative dans %.1fs : %s",
                task, model, attempt, MAX_RETRIES, delay, exc,
            )
            time.sleep(delay)
            continue

        usage = LLMUsage(
            task=task,
            model=model,
            input_tokens=getattr(response, "prompt_eval_count", 0) or 0,
            output_tokens=getattr(response, "eval_count", 0) or 0,
            duree_ms=(getattr(response, "total_duration", 0) or 0) / 1_000_000,
        )
        logger.info(
            "Appel LLM reussi (tache=%s, modele=%s, input_tokens=%d, output_tokens=%d, duree_ms=%.1f)",
            usage.task, usage.model, usage.input_tokens, usage.output_tokens, usage.duree_ms,
        )
        return response

    raise last_exc if last_exc is not None else RuntimeError("call_llm: aucune tentative effectuee")
