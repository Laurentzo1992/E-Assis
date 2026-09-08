"""Wrapper centralisé pour tous les appels LLM de kbbot.

Architecture hybride et configurable :
- En Production (PROD=true) : API Google Cloud Vertex AI avec le modèle Gemini
  (par défaut `gemini-3.1-flash-lite`), authentifié via un compte de service GCP
  (clé JSON située dans le même répertoire que le fichier `.env`).
- En Local / Développement (PROD=false) : Ollama local avec le modèle Llama
  (par défaut `llama3.1:8b`).

Tout appel LLM passe par `call_llm()`, qui centralise :
- La sélection transparente du backend et du modèle selon l'environnement ;
- Le retry/backoff exponentiel sur les erreurs transitoires (timeouts, 5xx, 429 rate-limit) ;
- Le logging structuré des tokens consommés et de la durée.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

try:
    import ollama
except ImportError:
    ollama = None  # type: ignore

from dotenv import find_dotenv, load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --- Variables d'Environnement ---

def is_prod() -> bool:
    """Indique si l'environnement d'exécution est la production."""
    val = os.getenv("PROD", "false").strip().lower()
    return val in ("true", "1", "yes", "on")


# Modèles selon le mode
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

_MODELES: dict[str, str] = {
    "extraction": LOCAL_LLM_MODEL,
    "redaction_whatsapp": LOCAL_LLM_MODEL,
    "verification_pertinence": LOCAL_LLM_MODEL,
    "traduction": LOCAL_LLM_MODEL,
}

# Configuration Ollama (Local)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT_S = 300.0

# Configuration Google Cloud / Gemini (Production)
GCP_SERVICE_ACCOUNT_JSON = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
GCP_LOCATION = os.getenv("GEMINI_LOCATION") or os.getenv("GCP_LOCATION") or "global"
GCP_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID") or os.getenv("GCP_PROJECT_ID", "")
GEMINI_TIMEOUT_S = 120.0

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
    """Levée quand `call_llm()` reçoit une `task` absente des modèles connus."""


def _resoudre_modele(task: str) -> str:
    if is_prod():
        return GEMINI_MODEL
    try:
        return _MODELES[task]
    except KeyError:
        raise TacheInconnue(f"Tâche LLM inconnue : {task!r}. Tâches disponibles : {sorted(_MODELES)}") from None


# --- Réponse normalisée -------------------------------------------------------------------------
# Même forme (response.message.content, prompt_eval_count, eval_count, total_duration en nanosecondes)
# pour compatibilité ascendante totale avec le reste du projet.


@dataclass
class _Message:
    content: str | None


@dataclass
class _ReponseNormalisee:
    message: _Message
    prompt_eval_count: int = 0
    eval_count: int = 0
    total_duration: int = 0  # nanosecondes


# --- Client Ollama (Local) ----------------------------------------------------------------------

_ollama_client_singleton: ollama.Client | None = None


def _get_default_client() -> Any:
    global _ollama_client_singleton
    if ollama is None:
        raise ImportError(
            "Le paquet 'ollama' est requis pour le mode local (PROD=false). "
            "Installez-le avec `pip install ollama` ou activez le mode production avec PROD=true."
        )
    if _ollama_client_singleton is None:
        _ollama_client_singleton = ollama.Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT_S)
    return _ollama_client_singleton


def _appeler_ollama(
    model: str, full_messages: list[dict[str, Any]], max_tokens: int, client: Any = None, **kwargs: Any
) -> _ReponseNormalisee:
    ollama_client = client if client is not None else _get_default_client()
    temperature = kwargs.pop("temperature", 0.1)
    raw_options = kwargs.pop("options", {})
    options = {"num_predict": max_tokens, "temperature": temperature, **raw_options}
    response = ollama_client.chat(model=model, messages=full_messages, options=options, **kwargs)
    return _ReponseNormalisee(
        message=_Message(content=response.message.content),
        prompt_eval_count=getattr(response, "prompt_eval_count", 0) or 0,
        eval_count=getattr(response, "eval_count", 0) or 0,
        total_duration=getattr(response, "total_duration", 0) or 0,
    )


# --- Client Google Cloud Vertex AI (Production) --------------------------------------------------

_gcp_credentials = None
_gcp_project_id: str | None = None


def _trouver_fichier_service_account() -> Path:
    """Localise le fichier JSON du compte de service dans le même répertoire que .env."""
    nom_fichier = GCP_SERVICE_ACCOUNT_JSON.strip()
    
    # 1. Chemin absolu direct
    p_direct = Path(nom_fichier)
    if p_direct.is_absolute() and p_direct.exists():
        return p_direct

    # 2. Dossier contenant le fichier .env
    env_path = find_dotenv()
    if env_path:
        p_env_dir = Path(env_path).parent / nom_fichier
        if p_env_dir.exists():
            return p_env_dir

    # 3. Répertoire racine E-Assis-main
    p_racine = Path(__file__).resolve().parent.parent / nom_fichier
    if p_racine.exists():
        return p_racine

    # 4. Répertoire de travail courant
    p_cwd = Path.cwd() / nom_fichier
    if p_cwd.exists():
        return p_cwd

    # 5. Répertoire api ou tmp (conteneur Docker)
    p_api = Path("/app/api") / nom_fichier
    if p_api.exists():
        return p_api

    p_tmp = Path("/tmp") / nom_fichier
    if p_tmp.exists():
        return p_tmp

    raise FileNotFoundError(
        f"Fichier de compte de service Google Cloud introuvable : '{nom_fichier}'. "
        f"Assurez-vous qu'il est placé dans le même répertoire que le fichier .env "
        f"et que la variable GCP_SERVICE_ACCOUNT_JSON est correctement renseignée."
    )


def _get_gcp_credentials():
    """Initialise et met en cache les identifiants du compte de service GCP."""
    global _gcp_credentials, _gcp_project_id
    if _gcp_credentials is None:
        try:
            from google.oauth2 import service_account
        except ImportError:
            raise ImportError(
                "Le paquet 'google-auth' est requis pour le mode production avec Google Cloud. "
                "Installez-le avec `pip install google-auth`."
            ) from None

        json_path = _trouver_fichier_service_account()
        logger.info("Chargement du compte de service GCP depuis : %s", json_path)
        
        with open(json_path, "r", encoding="utf-8") as f:
            sa_data = json.load(f)

        _gcp_project_id = GCP_PROJECT_ID.strip() or sa_data.get("project_id")
        if not _gcp_project_id:
            raise ValueError("project_id introuvable dans le fichier JSON du compte de service GCP.")

        _gcp_credentials = service_account.Credentials.from_service_account_info(
            sa_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    return _gcp_credentials, _gcp_project_id


def _obtenir_bearer_token() -> str:
    """Génère ou rafraîchit le token OAuth2 Google Cloud."""
    creds, _ = _get_gcp_credentials()
    from google.auth.transport.requests import Request
    if not creds.valid:
        creds.refresh(Request())
    return creds.token


def _appeler_gemini(
    model: str,
    messages: Sequence[Mapping[str, Any]],
    system: str | None,
    max_tokens: int,
    **kwargs: Any,
) -> _ReponseNormalisee:
    """Appelle l'API Google Cloud Vertex AI pour le modèle Gemini spécifié."""
    creds, project_id = _get_gcp_credentials()
    token = _obtenir_bearer_token()
    location = GCP_LOCATION
    if "gemini-3" in model or location in ("global", ""):
        location = "global"

    base_url = (
        "https://aiplatform.googleapis.com"
        if location == "global"
        else f"https://{location}-aiplatform.googleapis.com"
    )

    # Conversion des messages vers le format Gemini
    system_instruction = None
    contents = []

    if system:
        system_instruction = {"parts": [{"text": system}]}

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_instruction = {"parts": [{"text": content}]}
        elif role in ("user", "human"):
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role in ("assistant", "model"):
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.1),
        },
    }
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    endpoint = (
        f"{base_url}/v1/projects/{project_id}/"
        f"locations/{location}/publishers/google/models/{model}:generateContent"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "aistudio-build",
    }

    t0 = time.perf_counter_ns()
    with httpx.Client(timeout=GEMINI_TIMEOUT_S) as client:
        resp = client.post(endpoint, json=payload, headers=headers)
        # Fallback automatique vers location="global" si 404 sur une région spécifique
        if resp.status_code == 404 and location != "global":
            logger.warning("Modèle %s non trouvé dans la région %s (404), tentative avec location='global'...", model, location)
            endpoint_global = (
                f"https://aiplatform.googleapis.com/v1/projects/{project_id}/"
                f"locations/global/publishers/google/models/{model}:generateContent"
            )
            resp = client.post(endpoint_global, json=payload, headers=headers)
    t1 = time.perf_counter_ns()

    if resp.status_code != 200:
        logger.error("Erreur Vertex AI Gemini (%d) : %s", resp.status_code, resp.text)
        resp.raise_for_status()

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Réponse Vertex AI Gemini vide ou sans candidats : {data}")

    candidate_parts = candidates[0].get("content", {}).get("parts", [])
    texte_reponse = candidate_parts[0].get("text", "") if candidate_parts else ""

    usage_meta = data.get("usageMetadata", {})
    input_tokens = usage_meta.get("promptTokenCount", 0)
    output_tokens = usage_meta.get("candidatesTokenCount", 0)

    return _ReponseNormalisee(
        message=_Message(content=texte_reponse),
        prompt_eval_count=input_tokens,
        eval_count=output_tokens,
        total_duration=t1 - t0,
    )


# --- Gestion des Erreurs Transitoires ------------------------------------------------------------


def _est_erreur_transitoire(exc: Exception) -> bool:
    """Détermine si une erreur est passagère et justifie une nouvelle tentative."""
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # 429 = Rate limit (retry avec backoff), 5xx = Erreur serveur Google Cloud
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    if ollama is not None and isinstance(exc, getattr(ollama, "ResponseError", ())):
        return getattr(exc, "status_code", 500) >= 500
    return False


# --- Point d'entrée unique --------------------------------------------------------------------


def call_llm(
    task: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    system: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: Any = None,
    **kwargs: Any,
) -> _ReponseNormalisee:
    """Point d'entrée unique pour tout appel LLM dans kbbot.

    Bascule automatiquement entre Google Cloud Vertex AI (PROD=true) et Ollama local (PROD=false).
    Permet l'injection d'un faux client pour les tests unitaires.
    """
    model = _resoudre_modele(task)
    prod_active = is_prod()

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if prod_active and client is None:
                # Mode Production : Google Cloud Gemini
                response = _appeler_gemini(model, messages, system, max_tokens, **kwargs)
            else:
                # Mode Local ou Test : Ollama
                full_messages = list(messages)
                if system is not None:
                    full_messages = [{"role": "system", "content": system}, *full_messages]
                response = _appeler_ollama(model, full_messages, max_tokens, client, **kwargs)

        except Exception as exc:
            last_exc = exc
            if not _est_erreur_transitoire(exc) or attempt == MAX_RETRIES:
                logger.error(
                    "Appel LLM échoué définitivement (mode=%s, tâche=%s, modèle=%s, tentative=%d/%d) : %s",
                    "PROD" if prod_active else "LOCAL", task, model, attempt, MAX_RETRIES, exc,
                )
                raise
            delay = min(BASE_DELAY_S * (2 ** (attempt - 1)) + random.uniform(0, 1), MAX_DELAY_S)
            logger.warning(
                "Erreur transitoire LLM (mode=%s, tâche=%s, modèle=%s, tentative=%d/%d) - "
                "nouvelle tentative dans %.1fs : %s",
                "PROD" if prod_active else "LOCAL", task, model, attempt, MAX_RETRIES, delay, exc,
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
            "Appel LLM réussi (mode=%s, tâche=%s, modèle=%s, input_tokens=%d, output_tokens=%d, durée_ms=%.1f)",
            "PROD" if prod_active else "LOCAL", usage.task, usage.model, usage.input_tokens, usage.output_tokens, usage.duree_ms,
        )
        return response

    raise last_exc if last_exc is not None else RuntimeError("call_llm: aucune tentative effectuée")
