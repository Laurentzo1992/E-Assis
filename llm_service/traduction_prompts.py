"""Traduction integrale d'un texte administratif brut (typiquement `Marche.objet`) vers une autre
langue - contrairement a `llm_service.whatsapp_prompts.resumer_objet`, aucune contrainte de
longueur ni de schema JSON ici : juste une traduction fidele, texte brut en sortie.

Utilise pour le contenu EMAIL d'une alerte d'appel d'offre quand `Entreprise.langue_alertes` n'est
pas le francais (cf. `api/scripts/match_and_alert.py::_envoyer_alerte`).
"""

import logging

from llm_service.llm_client import call_llm

logger = logging.getLogger(__name__)

TASK = "traduction"

_NOMS_LANGUES: dict[str, str] = {
    "en": "anglais",
    "mos": "mooré (langue mossi du Burkina Faso)",
}


class TraductionEchouee(RuntimeError):
    """Levee quand le LLM renvoie une reponse vide pour une traduction, meme apres retry."""


def _system_prompt(langue_cible: str) -> str:
    nom_langue = _NOMS_LANGUES.get(langue_cible, langue_cible)
    return (
        f"Tu traduis fidelement un texte administratif du francais vers le {nom_langue}, sans "
        "rien ajouter ni omettre. Reponds uniquement avec le texte traduit (pas de JSON ici, "
        "texte brut)."
    )


def traduire_texte(texte: str, langue_cible: str) -> str:
    """Traduit `texte` vers `langue_cible`. Retourne `texte` tel quel SANS appel LLM si
    `langue_cible == "fr"` (evite un aller-retour inutile - le texte source est deja en francais).
    Retente une fois sur reponse vide, meme pattern que `resumer_objet`."""
    if langue_cible == "fr":
        return texte

    system = _system_prompt(langue_cible)
    response = call_llm(TASK, messages=[{"role": "user", "content": texte}], system=system)
    contenu = (response.message.content or "").strip()
    if contenu:
        return contenu

    logger.warning("Reponse vide du LLM pour la traduction vers %s, nouvelle tentative.", langue_cible)
    response_retry = call_llm(TASK, messages=[{"role": "user", "content": texte}], system=system)
    contenu_retry = (response_retry.message.content or "").strip()
    if contenu_retry:
        return contenu_retry

    raise TraductionEchouee(f"Traduction vers {langue_cible!r} vide apres une tentative de correction.")
