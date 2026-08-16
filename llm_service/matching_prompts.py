"""Verification de pertinence d'un marche candidat (retenu par recherche vectorielle) contre le
profil d'une entreprise, en complement du score cosinus (cf. api/scripts/match_and_alert.py,
_traiter_appels_offre).

Le score semantique mesure une proximite de sens globale, pas une pertinence reelle : un marche
peut partager du vocabulaire avec le profil sans que l'entreprise puisse raisonnablement y
repondre (constate en reel : un profil "informatique/securite" matchant un tableau d'evaluation
de scanners sans rapport avec l'entreprise alertee, cf. docstring de module de
match_and_alert.py). Ce module sert de second filtre, applique uniquement aux candidats deja
retenus par le score semantique/lexical - jamais un remplacement de la recherche vectorielle,
juste un raffinement de precision sur un petit nombre de candidats (5-8 max par entreprise).
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from llm_service.llm_client import call_llm

logger = logging.getLogger(__name__)

TASK = "verification_pertinence"

SYSTEM_PROMPT = """Tu juges si un marche public correspond reellement au profil d'activite \
d'une entreprise, en francais.

On te donne le profil de l'entreprise (domaines/secteurs d'activite declares) et l'objet d'un \
marche public deja retenu par une recherche automatique comme candidat plausible - qui peut etre \
un faux positif (ex. un marche partage du vocabulaire avec le profil sans que l'entreprise \
puisse raisonnablement y repondre, comme un tableau d'evaluation de materiel plutot qu'un appel \
a fournir ce materiel).

Compare le SECTEUR/THEME general du marche a celui du profil, jamais une correspondance exacte de \
sous-categorie ou de formulation - mais exige que l'objet du marche NOMME explicitement quelque \
chose du secteur declare (informatique, logiciel, systeme, reseau, securite, etc.), pas juste une \
proximite plausible.

Exemple ou pertinent=true : profil contenant "Acquisition des equipements, securite informatique, \
logiciel, systeme" et marche "Acquisition, installation et mise en service de MATERIELS \
INFORMATIQUES" -> le mot "informatique" est present dans l'objet, meme secteur que le profil \
(materiel et logiciel informatique appartiennent au meme secteur, ne les traite jamais comme des \
domaines distincts).

Exemple ou pertinent=false malgre un profil "Informatique" : marche "Fourniture de bureau" (aucun \
mot du secteur informatique/technique dans l'objet - juste des fournitures generiques, papeterie, \
mobilier) -> reste hors-sujet, MEME SI l'entreprise achete elle-meme parfois ce genre de biens \
pour son propre usage. Le simple fait qu'un profil contienne "Informatique" ne rend pas pertinent \
n'importe quel marche d'achat generique (bureau, mobilier, climatiseurs, travaux, restauration) - \
il faut un terme concret du secteur declare dans l'objet du marche lui-meme.

Reponds UNIQUEMENT avec un objet JSON valide (aucun texte avant/apres, aucun bloc markdown \
```json) :

{"pertinent": bool, "raison": string}

"pertinent" = true seulement si une entreprise de ce profil pourrait raisonnablement \
soumissionner a ce marche. En cas de doute raisonnable, reponds true : ce filtre ne doit ecarter \
que les cas clairement hors-sujet (changement de secteur), jamais une simple difference de \
formulation a l'interieur du meme secteur."""


class VerdictPertinence(BaseModel):
    pertinent: bool
    raison: str


class VerificationEchouee(RuntimeError):
    """Levee quand le LLM ne produit pas un JSON valide selon `VerdictPertinence`, meme apres retry."""


def _nettoyer_json(texte: str) -> str:
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return texte


def _valider_verdict(texte_reponse: str | None) -> VerdictPertinence:
    if not texte_reponse:
        raise VerificationEchouee("La reponse du LLM ne contient aucun texte exploitable.")
    data = json.loads(_nettoyer_json(texte_reponse))
    return VerdictPertinence.model_validate(data)


def verifier_pertinence(libelles_profil: list[str], objet_marche: str) -> bool:
    """Juge si `objet_marche` correspond reellement au profil (`libelles_profil`, domaines+secteurs
    de l'entreprise). Retente une fois si la reponse n'est pas un JSON valide ; leve
    `VerificationEchouee` si la seconde tentative echoue aussi - a l'appelant de decider du
    comportement par defaut (fail-open recommande, pour ne jamais perdre une opportunite reelle a
    cause d'un simple hoquet du LLM, cf. api/scripts/match_and_alert.py)."""
    profil_txt = ", ".join(libelles_profil)
    prompt = f"Profil de l'entreprise : {profil_txt}\n\nObjet du marche candidat :\n{objet_marche}"
    response = call_llm(TASK, messages=[{"role": "user", "content": prompt}], system=SYSTEM_PROMPT)

    try:
        return _valider_verdict(response.message.content).pertinent
    except (json.JSONDecodeError, ValidationError, VerificationEchouee) as premiere_erreur:
        logger.warning(
            "Reponse LLM invalide pour la verification de pertinence, nouvelle tentative avec l'erreur explicite : %s",
            premiere_erreur,
        )
        prompt_retry = (
            f"{prompt}\n\n"
            f"ATTENTION : ta reponse precedente etait invalide ({premiere_erreur}). "
            "Reponds UNIQUEMENT avec l'objet JSON demande, sans texte avant/apres, sans bloc markdown."
        )
        response_retry = call_llm(TASK, messages=[{"role": "user", "content": prompt_retry}], system=SYSTEM_PROMPT)

        try:
            return _valider_verdict(response_retry.message.content).pertinent
        except (json.JSONDecodeError, ValidationError, VerificationEchouee) as seconde_erreur:
            raise VerificationEchouee(
                f"Verification de pertinence invalide apres une tentative de correction : {seconde_erreur}"
            ) from seconde_erreur
