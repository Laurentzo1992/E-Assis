"""Redaction de la variable "resume" d'un modele WhatsApp approuve par Meta - jamais de texte
libre pour le message entier.

Le LLM ne fait que resumer l'objet du marche matche en une phrase courte (<=100 caracteres,
lisible sur WhatsApp). L'organisme et le nom de l'entreprise sont toujours repris tels quels dans
`api/scripts/match_and_alert.py`, jamais reformules par le LLM - lecon documentee dans
fasofoodalert-core : un nom d'organisation reformule par un LLM peut glisser vers une autre
organisation (ex. "International Rescue Committee" -> "Comite international de la Croix-Rouge").
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from llm_service.llm_client import call_llm

logger = logging.getLogger(__name__)

TASK = "redaction_whatsapp"

SYSTEM_PROMPT = """Tu resumes un avis de marche public en une phrase courte et concrete, en \
francais, pour la variable d'un message WhatsApp (100 caracteres maximum).

Reponds UNIQUEMENT avec un objet JSON valide (aucun texte avant/apres, aucun bloc markdown \
```json) :

{"resume": string}

Ne mentionne pas le nom de l'organisme (deja indique separement dans le message). Ne depasse \
jamais 100 caracteres. N'invente aucune information absente du texte fourni."""


class ResumeAvis(BaseModel):
    resume: str


class RedactionEchouee(RuntimeError):
    """Levee quand le LLM ne produit pas un JSON valide selon `ResumeAvis`, meme apres retry."""


def _nettoyer_json(texte: str) -> str:
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return texte


def _valider_resume(texte_reponse: str | None) -> str:
    if not texte_reponse:
        raise RedactionEchouee("La reponse du LLM ne contient aucun texte exploitable.")
    data = json.loads(_nettoyer_json(texte_reponse))
    return ResumeAvis.model_validate(data).resume[:100]


def resumer_objet(objet: str) -> str:
    """Resume `objet` (texte de l'avis matche par recherche vectorielle) en une phrase courte
    pour la variable de template WhatsApp. Retente une fois si la reponse n'est pas un JSON
    valide ; leve `RedactionEchouee` si la seconde tentative echoue aussi."""
    prompt = f"Objet du marche :\n\n{objet}"
    response = call_llm(TASK, messages=[{"role": "user", "content": prompt}], system=SYSTEM_PROMPT)

    try:
        return _valider_resume(response.message.content)
    except (json.JSONDecodeError, ValidationError, RedactionEchouee) as premiere_erreur:
        logger.warning(
            "Reponse LLM invalide pour le resume WhatsApp, nouvelle tentative avec l'erreur explicite : %s",
            premiere_erreur,
        )
        prompt_retry = (
            f"{prompt}\n\n"
            f"ATTENTION : ta reponse precedente etait invalide ({premiere_erreur}). "
            "Reponds UNIQUEMENT avec l'objet JSON demande, sans texte avant/apres, sans bloc markdown."
        )
        response_retry = call_llm(TASK, messages=[{"role": "user", "content": prompt_retry}], system=SYSTEM_PROMPT)

        try:
            return _valider_resume(response_retry.message.content)
        except (json.JSONDecodeError, ValidationError, RedactionEchouee) as seconde_erreur:
            raise RedactionEchouee(
                f"Redaction du resume WhatsApp invalide apres une tentative de correction : {seconde_erreur}"
            ) from seconde_erreur
