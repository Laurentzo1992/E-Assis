"""Redaction de la variable "resume" d'un modele WhatsApp approuve par Meta - jamais de texte
libre pour le message entier.

Le LLM ne fait que resumer l'objet du marche matche en une phrase courte (<=300 caracteres,
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
francais, pour la variable d'un message WhatsApp (300 caracteres maximum).

Reponds UNIQUEMENT avec un objet JSON valide (aucun texte avant/apres, aucun bloc markdown \
```json) :

{"resume": string}

Ne mentionne pas le nom de l'organisme (deja indique separement dans le message). Ne depasse \
jamais 300 caracteres. N'invente aucune information absente du texte fourni."""

SYSTEM_PROMPT_EN = """You summarize a public procurement notice in one short, concrete sentence, \
in English, for the variable of a WhatsApp message (300 characters maximum).

Respond ONLY with a valid JSON object (no text before/after, no ```json markdown block):

{"resume": string}

Do not mention the name of the organization (already given separately in the message). Never \
exceed 300 characters. Do not invent any information absent from the provided text."""

# Traduction moore best-effort (LLM), non verifiee par un locuteur natif - a valider avant mise en
# production reelle (cf. plan multilingue : aucun outil de traduction fiable n'existe pour cette
# langue a faible ressource, decision utilisateur de livrer une premiere version best-effort
# plutot que de bloquer sur une traduction que je ne peux pas verifier moi-meme).
SYSTEM_PROMPT_MOS = """Fo yaa yaool n yaa marse-koeese sebre yell-yagre a ye tɩ yaa koɛɛg sẽn \
yaa vale, yaa mooré, yaa WhatsApp koɛɛg pʋgẽ (bũmb 300 tɛka).

Leb-y bal ne JSON sõma (ka gomd n deng bɩ n pʋg ye, ka ```json block ye):

{"resume": string}

Ra togs-y tʋʋm-doog yʋʋre ye (b tara wilgame a to pʋgẽ). Ra kẽ bũmb 300 tɛka ye. Ra pa paas-y \
bũmb sẽn ka be gʋlsg pʋgẽ ye."""

_SYSTEM_PROMPTS_PAR_LANGUE: dict[str, str] = {
    "fr": SYSTEM_PROMPT,
    "en": SYSTEM_PROMPT_EN,
    "mos": SYSTEM_PROMPT_MOS,
}


class ResumeAvis(BaseModel):
    resume: str


class RedactionEchouee(RuntimeError):
    """Levee quand le LLM ne produit pas un JSON valide selon `ResumeAvis`, meme apres retry."""


def _nettoyer_json(texte: str) -> str:
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return texte


def _troncature_mot(texte: str, longueur: int) -> str:
    """Tronque au dernier espace avant `longueur` caracteres (jamais au milieu d'un mot) - un
    simple `texte[:longueur]` produit un mot coupe illisible dans le message WhatsApp final,
    meme si le LLM a normalement deja pour consigne de rester sous cette limite (garde-fou pour
    les cas ou il la depasse legerement malgre tout)."""
    if len(texte) <= longueur:
        return texte
    tronque = texte[:longueur]
    dernier_espace = tronque.rfind(" ")
    if dernier_espace > 0:
        tronque = tronque[:dernier_espace]
    return tronque.rstrip(",.;:") + "..."


def _valider_resume(texte_reponse: str | None) -> str:
    if not texte_reponse:
        raise RedactionEchouee("La reponse du LLM ne contient aucun texte exploitable.")
    data = json.loads(_nettoyer_json(texte_reponse))
    return _troncature_mot(ResumeAvis.model_validate(data).resume, 300)


def resumer_objet(objet: str, langue: str = "fr") -> str:
    """Resume `objet` (texte de l'avis matche par recherche vectorielle) en une phrase courte
    pour la variable de template WhatsApp, redigee dans `langue` ("fr"/"en"/"mos" - repli sur le
    francais si inconnue). Retente une fois si la reponse n'est pas un JSON valide ; leve
    `RedactionEchouee` si la seconde tentative echoue aussi."""
    system_prompt = _SYSTEM_PROMPTS_PAR_LANGUE.get(langue, SYSTEM_PROMPT)
    prompt = f"Objet du marche :\n\n{objet}"
    response = call_llm(TASK, messages=[{"role": "user", "content": prompt}], system=system_prompt)

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
        response_retry = call_llm(TASK, messages=[{"role": "user", "content": prompt_retry}], system=system_prompt)

        try:
            return _valider_resume(response_retry.message.content)
        except (json.JSONDecodeError, ValidationError, RedactionEchouee) as seconde_erreur:
            raise RedactionEchouee(
                f"Redaction du resume WhatsApp invalide apres une tentative de correction : {seconde_erreur}"
            ) from seconde_erreur
