"""Wrapper centralise pour tous les appels LLM de kbbot.

Pattern repris tel quel de fasofoodalert-core/llm_service/llm_client.py (deja en production dans
ce projet voisin, meme choix d'architecture initial : Ollama auto-heberge plutot qu'une API
payante, pour le cout et la souverainete des donnees des entreprises inscrites).

Tout appel LLM passe par `call_llm()`, qui centralise :
- la selection du modele par tache (`_resoudre_modele`) ;
- le retry/backoff exponentiel sur les erreurs transitoires (serveur injoignable, erreurs 5xx,
  429 rate-limit) - les erreurs non transitoires (modele absent, requete invalide, tache
  inconnue...) ne sont jamais retentees ;
- le logging structure des tokens consommes et de la duree, pour chaque appel reussi.

100% local via Ollama (GPU partage avec vision-ocr/DeepSeek-OCR). Constate en reel sur le
bulletin n°4458 (66 sections) : mistral:7b (60 marches, 4 echecs), mistral-nemo:12b apres
correctif du bug `{}`/`[]` (54 marches, 1 echec - le meilleur des trois testes), qwen2.5:14b
(48 marches, 4 echecs). Aucun n'est parfait : plusieurs hallucinations reelles constatees malgre
la consigne explicite de ne jamais inventer, compensees cote deterministe par des filtres
pre-LLM (cf. api/scripts/extract_bulletin.py, _semble_repertoire_fournisseurs/_semble_trop_courte).

Le 12/08/2026, qwen3:14b (mode raisonnement) teste sur 6 sections reelles du bulletin n°4464 en
CPU (docker-compose.llm.yml, profil "cpu") : nettement pire que mistral-nemo:12b sur ce meme
echantillon - 3 avis extraits contre 6, 1 echec par timeout complet (~20 min avant abandon apres
epuisement des retries, sur une section qui n'a pourtant pris que 69.6s a mistral-nemo:12b), et
5.5x plus lent en moyenne (354.2s/section contre 64.7s/section). Le temps de "reflexion" du mode
raisonnement semble consomme sans gain de qualite correspondant sur cette tache d'extraction
structuree - prolonge le constat deja fait avec qwen2.5:14b. mistral-nemo:12b reste le modele de
production pour cette tache.

Le 08/08/2026, Gemini et Claude (API cloud) ont ete testes pour reduire ces hallucinations et la
charge de calcul locale (soupconnee dans plusieurs plantages Docker Desktop le 07/08/2026) - les
deux abandonnes le jour-meme (quota gratuit Gemini limite a 20 requetes/jour, credit insuffisant
sur la cle Anthropic testee) et retires de ce fichier. Retour au 100% local.
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import ollama
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_MODELES: dict[str, str] = {
    "extraction": "mistral-nemo:12b",
    "redaction_whatsapp": "mistral:7b",
    # mistral:7b initialement, remplace apres constat en reel (bulletin 4466) : jugeait
    # systematiquement "non pertinent" des correspondances evidentes (ex. "Acquisition de
    # materiels informatiques" rejete pour un profil listant "Acquisition des equipements,
    # logiciel, systeme, securite informatique") - la tache demande une nuance ("meme secteur,
    # formulation differente") que ce modele ne suit pas de facon fiable, meme avec un prompt
    # explicite. mistral-nemo:12b, deja le modele de production pour l'extraction (tache qui
    # demande le meme type de jugement nuance), corrige ces faux negatifs en pratique.
    "verification_pertinence": "mistral-nemo:12b",
    "traduction": "mistral:7b",
}

# "ollama" = nom du service dans docker-compose.llm.yml (reseau Docker "backend") ; "localhost"
# suppose un usage depuis l'hote directement.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Sans timeout, ollama.Client() (httpx en interne) attend indefiniment - constate en reel sur le
# bulletin 4462 : une requete bloquee sur la section "COMMUNE DE KOUNDOUGOU" a fige l'extraction
# pendant plus de 3h, deux fois de suite sur la meme section, sans qu'aucune erreur ne remonte
# jamais (0% CPU, aucune progression) jusqu'a ce qu'Airflow finisse par tuer la tache comme
# "zombie". Une requete d'extraction legitime observee jusqu'ici prend au plus ~90s ; 300s laisse
# une marge confortable tout en bornant le pire cas a des minutes plutot que des heures.
OLLAMA_TIMEOUT_S = 300.0

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
    """Levee quand `call_llm()` recoit une `task` absente des modeles connus."""


def _resoudre_modele(task: str) -> str:
    try:
        return _MODELES[task]
    except KeyError:
        raise TacheInconnue(f"Tache LLM inconnue : {task!r}. Taches disponibles : {sorted(_MODELES)}") from None


# --- Reponse normalisee -------------------------------------------------------------------------
# Meme forme (`response.message.content`, `prompt_eval_count`, `eval_count`, `total_duration` en
# nanosecondes) que celle native d'Ollama, pour qu'extraction_prompts.py/whatsapp_prompts.py -
# qui ne lisent que ces champs - n'aient jamais besoin de savoir quel client a repondu.


@dataclass
class _Message:
    content: str | None


@dataclass
class _ReponseNormalisee:
    message: _Message
    prompt_eval_count: int = 0
    eval_count: int = 0
    total_duration: int = 0  # nanosecondes, comme Ollama


# --- Ollama ---------------------------------------------------------------------------------


_client_singleton: ollama.Client | None = None


def _get_default_client() -> ollama.Client:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = ollama.Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT_S)
    return _client_singleton


def _est_erreur_transitoire(exc: Exception) -> bool:
    if isinstance(exc, ConnectionError):
        return True
    # httpx.TimeoutException/TransportError : ce que leve reellement le client (httpx en interne)
    # sur un depassement de OLLAMA_TIMEOUT_S ou une connexion coupee - une requete qui prenait
    # simplement plus longtemps que d'habitude doit pouvoir etre retentee comme n'importe quelle
    # autre erreur reseau transitoire, pas traitee comme un echec definitif.
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    if isinstance(exc, ollama.ResponseError):
        return exc.status_code >= 500
    return False


def _appeler_ollama(
    model: str, full_messages: list[dict[str, Any]], max_tokens: int, client: ollama.Client | None, **kwargs: Any
) -> _ReponseNormalisee:
    ollama_client = client if client is not None else _get_default_client()
    options = {"num_predict": max_tokens, **kwargs.pop("options", {})}
    response = ollama_client.chat(model=model, messages=full_messages, options=options, **kwargs)
    return _ReponseNormalisee(
        message=_Message(content=response.message.content),
        prompt_eval_count=getattr(response, "prompt_eval_count", 0) or 0,
        eval_count=getattr(response, "eval_count", 0) or 0,
        total_duration=getattr(response, "total_duration", 0) or 0,
    )


# --- Point d'entree unique --------------------------------------------------------------------


def call_llm(
    task: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    system: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: ollama.Client | None = None,
    **kwargs: Any,
) -> _ReponseNormalisee:
    """Point d'entree unique pour tout appel LLM dans kbbot.

    `client` permet d'injecter un client Ollama (ou un mock dans les tests). La reponse est
    toujours une `_ReponseNormalisee` (`response.message.content`).
    """
    model = _resoudre_modele(task)

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            full_messages = list(messages)
            if system is not None:
                full_messages = [{"role": "system", "content": system}, *full_messages]
            response = _appeler_ollama(model, full_messages, max_tokens, client, **kwargs)
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
                "Erreur transitoire LLM (tache=%s, modele=%s, tentative=%d/%d) - "
                "nouvelle tentative dans %.1fs : %s",
                task, model, attempt, MAX_RETRIES, delay, exc,
            )
            time.sleep(delay)
            continue

        usage = LLMUsage(
            task=task,
            model=model,
            input_tokens=response.prompt_eval_count,
            output_tokens=response.eval_count,
            duree_ms=response.total_duration / 1_000_000,
        )
        logger.info(
            "Appel LLM reussi (tache=%s, modele=%s, input_tokens=%d, output_tokens=%d, duree_ms=%.1f)",
            usage.task, usage.model, usage.input_tokens, usage.output_tokens, usage.duree_ms,
        )
        return response

    raise last_exc if last_exc is not None else RuntimeError("call_llm: aucune tentative effectuee")
