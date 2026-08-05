"""Extraction structuree d'avis de marche/resultat depuis le texte d'un bulletin DGCMEF.

Meme pattern que fasofoodalert-core/llm_service/agents/indicator_extractor.py : schema JSON
impose dans le prompt, reponse validee avec Pydantic, une seule relance corrective si la
validation echoue, sinon `ExtractionEchouee`. Le texte fourni est un groupe de chunks partageant
le meme `section_title` (proxy d'un avis - cf. ingestion/chunking.py, deja documente comme une
heuristique imparfaite sur les pages a forte densite de tableaux : c'est pour ca que le prompt
autorise explicitement a repondre par une liste vide plutot que d'inventer un avis a partir de
texte qui n'en est pas un, ex. une ligne de classement d'entreprises).

Revise apres un premier run reel sur le bulletin n°4456 (310 avis extraits, ~90 echecs analyses) :
- `date_avis` accepte desormais n'importe quelle chaine (parsee tolerant cote Python, cf.
  `parse_llm_date`) plutot qu'un `date` Pydantic strict - la majorite des echecs constates
  venaient du LLM renvoyant "Non specifiee", "20XX-00-00", une annee seule, ou confondant un
  numero RCCM/IFU avec une date, ce qui faisait echouer toute l'extraction pour ce seul champ.
- `type_avis` est normalise depuis des synonymes reels observes ("retenu", "conforme",
  "demande_prix"...) avant validation, en plus d'exemples ajoutes au prompt.
- `format="json"` force la sortie JSON native d'Ollama (evite les guillemets simples/texte
  parasite qui causaient ~15% des echecs).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ValidationError

from llm_service.llm_client import call_llm

logger = logging.getLogger(__name__)

TASK = "extraction"

SYSTEM_PROMPT = """Tu es un extracteur d'avis de marches publics pour le Burkina Faso, a partir \
d'extraits du bulletin "Quotidien des marches publics" (DGCMEF).

A partir du texte fourni, identifie si il s'agit d'un avis de marche exploitable (appel d'offres,
demande de prix, resultat d'attribution...) et extrait ses informations. Le texte peut aussi etre
du bruit (en-tete de page, ligne de tableau isolee, sommaire) - dans ce cas reponds avec un
tableau vide.

Reponds UNIQUEMENT avec un tableau JSON valide (aucun texte avant/apres, aucun bloc markdown \
```json), ou chaque element respecte exactement ce schema :

{
  "type_avis": "appel_offre" | "resultat" | "autre",
  "organisme": string,              // autorite contractante / organisme emetteur
  "objet": string,                  // objet du marche, resume en une phrase
  "type_procedure": string | null,  // ex. "demande de prix", "appel d'offres ouvert"
  "montant_min": number | null,     // montant en FCFA si mentionne
  "montant_max": number | null,
  "date_avis": string | null,       // date pertinente (ouverture, publication...), ISO 8601 AAAA-MM-JJ
  "entreprise_attributaire_nom": string | null,  // uniquement si type_avis == "resultat" et un attributaire est nomme
  "montant_attribue": number | null               // uniquement si type_avis == "resultat"
}

"type_avis" doit valoir EXACTEMENT "appel_offre", "resultat" ou "autre" - jamais un autre mot.
Traduis le vocabulaire du texte vers ces 3 categories : "retenu", "attributaire", "conforme",
"resultat provisoire/definitif" -> "resultat" ; "demande de prix", "appel d'offres", "avis" \
-> "appel_offre" ; une ligne de tableau/classement sans structure d'avis -> "autre".

"date_avis" doit etre soit une vraie date (jour/mois/annee explicites dans le texte), soit null.
Ne mets JAMAIS "non specifiee", une annee seule, ou un numero de reference/RCCM/IFU a la place
d'une date - dans ces cas, mets null.

"montant_attribue"/"montant_min"/"montant_max" doivent etre des nombres en FCFA, jamais un numero
de telephone ou une reference.

Si le texte ne decrit aucun avis de marche exploitable, reponds avec un tableau vide : []
Ne devine jamais une valeur (organisme, montant, date...) qui n'est pas explicitement dans le texte."""

_TYPE_AVIS_SYNONYMES = {
    "retenu": "resultat", "non retenu": "resultat", "conforme": "resultat",
    "non conforme": "resultat", "attributaire": "resultat", "resultat provisoire": "resultat",
    "resultat definitif": "resultat", "demande_prix": "appel_offre", "demande de prix": "appel_offre",
    "appel d'offres": "appel_offre", "appel_offres": "appel_offre", "avis": "appel_offre",
}


class AvisExtrait(BaseModel):
    type_avis: Literal["appel_offre", "resultat", "autre"]
    organisme: str
    objet: str
    type_procedure: str | None = None
    montant_min: float | None = None
    montant_max: float | None = None
    date_avis: str | None = None
    entreprise_attributaire_nom: str | None = None
    montant_attribue: float | None = None


class ExtractionEchouee(RuntimeError):
    """Levee quand le LLM ne produit pas un JSON valide selon `AvisExtrait`, meme apres retry."""


_ANNEE_SEULE = re.compile(r"^\d{4}$")


def parse_llm_date(raw: str | None) -> date | None:
    """Parsing tolerant de `AvisExtrait.date_avis` (texte libre cote LLM) - retourne None sur
    tout ce qui n'est pas clairement une date plutot que de lever, cf. echecs reels observes
    ("Non specifiee", "20XX-00-00", annee seule, RCCM/IFU confondu avec une date)."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass
    if _ANNEE_SEULE.fullmatch(raw):
        return date(int(raw), 1, 1)
    return None


def _extraire_texte_reponse(response) -> str:
    texte = response.message.content
    if not texte:
        raise ExtractionEchouee("La reponse du LLM ne contient aucun texte exploitable.")
    return texte


def _nettoyer_json(texte: str) -> str:
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return texte


def _normaliser_type_avis(item: dict) -> dict:
    valeur = str(item.get("type_avis", "")).strip().lower()
    if valeur in _TYPE_AVIS_SYNONYMES:
        item["type_avis"] = _TYPE_AVIS_SYNONYMES[valeur]
    return item


def _valider_avis(texte_json: str) -> list[AvisExtrait]:
    data = json.loads(_nettoyer_json(texte_json))
    if isinstance(data, dict):
        # format="json" (mode JSON natif d'Ollama, ajoute pour eliminer le JSON syntaxiquement
        # invalide) a un effet de bord constate en reel : le modele enveloppe alors souvent la
        # liste sous une cle arbitraire ("avis_1", "avises", "appel_offre"...) au lieu du tableau
        # nu demande dans le prompt. On ne peut pas deviner le nom de cette cle a l'avance, donc
        # si l'objet n'a qu'une seule cle, on en prend la valeur telle quelle (liste ou objet
        # unique) plutot que de se limiter a une seule cle fixe ("avis").
        if len(data) == 0:
            # Certains modeles (mistral-nemo, qwen2.5 constates en reel) renvoient `{}` au lieu du
            # tableau vide `[]` demande par le prompt quand la section ne contient aucun avis -
            # sans ce cas, `else: data = [data]` tentait de valider `{}` comme un AvisExtrait
            # complet et echouait systematiquement (tous les champs obligatoires manquants).
            data = []
        elif len(data) == 1:
            value = next(iter(data.values()))
            data = value if isinstance(value, list) else [value]
        else:
            data = [data]
    # Constate en reel avec mistral-nemo:12b sur un bulletin dense (181 sections) : le tableau
    # contient parfois un element qui n'est pas un objet (une chaine brute), ce qui faisait
    # planter tout `extract_bulletin()` (AttributeError non rattrapee, hors de la boucle
    # try/except par section) au lieu de simplement ignorer cet element comme du bruit.
    data = [item for item in data if isinstance(item, dict)]
    return [AvisExtrait.model_validate(_normaliser_type_avis(item)) for item in data]


def extraire_avis(texte_section: str) -> list[AvisExtrait]:
    """Extrait les avis de marche presents dans `texte_section` (un groupe de chunks d'un meme
    `section_title`). Retourne une liste (eventuellement vide). Retente une fois si la premiere
    reponse n'est pas un JSON valide ; leve `ExtractionEchouee` si la seconde tentative echoue."""
    prompt = f"Texte du bulletin :\n\n{texte_section}"
    response = call_llm(TASK, messages=[{"role": "user", "content": prompt}], system=SYSTEM_PROMPT, format="json")
    texte_reponse = _extraire_texte_reponse(response)

    try:
        return _valider_avis(texte_reponse)
    except (json.JSONDecodeError, ValidationError) as premiere_erreur:
        logger.warning(
            "Reponse LLM invalide pour l'extraction d'avis, nouvelle tentative avec l'erreur explicite : %s",
            premiere_erreur,
        )
        prompt_retry = (
            f"{prompt}\n\n"
            f"ATTENTION : ta reponse precedente etait invalide ({premiere_erreur}). "
            "Reponds UNIQUEMENT avec un tableau JSON valide respectant exactement le schema demande, "
            "sans texte avant/apres, sans bloc markdown."
        )
        response_retry = call_llm(
            TASK, messages=[{"role": "user", "content": prompt_retry}], system=SYSTEM_PROMPT, format="json"
        )
        texte_reponse_retry = _extraire_texte_reponse(response_retry)

        try:
            return _valider_avis(texte_reponse_retry)
        except (json.JSONDecodeError, ValidationError) as seconde_erreur:
            raise ExtractionEchouee(
                f"Extraction d'avis invalide apres une tentative de correction : {seconde_erreur}"
            ) from seconde_erreur
