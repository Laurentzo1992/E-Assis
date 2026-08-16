"""Extraction structuree d'avis de marche/resultat depuis le texte d'un bulletin DGCMEF.

Meme pattern que fasofoodalert-core/llm_service/agents/indicator_extractor.py : schema JSON
impose dans le prompt, reponse validee avec Pydantic, une seule relance corrective si la
validation echoue, sinon `ExtractionEchouee`. Le texte fourni est un groupe de chunks partageant
le meme `section_title` (proxy d'un avis - cf. ingestion/chunking.py, deja documente comme une
heuristique imparfaite sur les pages a forte densite de tableaux : c'est pour ca que le prompt
autorise explicitement a repondre par une liste vide plutot que d'inventer un avis a partir de
texte qui n'en est pas un, ex. une ligne de classement d'entreprises).

Trois prompts, pas un seul (ajoute le 13/08/2026) : `extraire_resultat`/`extraire_appel_offre`
sont utilises quand `api/scripts/extract_bulletin._detecter_type_avis` a deja tranche le type avec
certitude via des marqueurs textuels fiables - le LLM n'a alors plus besoin de classifier (retire
du schema/prompt), et le schema est restreint aux seuls champs pertinents pour ce type (ex. pas de
champs "entreprise_attributaire_*" dans le prompt appel_offre, denues de sens pour une nouvelle
opportunite). `extraire_avis` (le prompt generique complet, avec classification) reste le repli
pour les sections ambigues (marqueurs des deux types presents, ou aucun). Avant ce changement,
une mauvaise classification LLM etait corrigee a posteriori (`_corriger_type_avis`, retire) en
ne reecrivant QUE le label `type_avis` - les champs deja extraits sous la mauvaise hypothese (ex.
attributaire jamais cherche parce que le LLM pensait extraire un appel d'offre) restaient faux ou
manquants malgre la "correction". Trancher le type AVANT l'appel LLM elimine cette classe d'erreur
a la source plutot que de la corriger apres coup.

Revise apres un premier run reel sur le bulletin n°4456 (310 avis extraits, ~90 echecs analyses) :
- `date_avis` accepte desormais n'importe quelle chaine (parsee tolerant cote Python, cf.
  `parse_llm_date`) plutot qu'un `date` Pydantic strict - la majorite des echecs constates
  venaient du LLM renvoyant "Non specifiee", "20XX-00-00", une annee seule, ou confondant un
  numero RCCM/IFU avec une date, ce qui faisait echouer toute l'extraction pour ce seul champ.
- `type_avis` est normalise depuis des synonymes reels observes ("retenu", "conforme",
  "demande_prix"...) avant validation, en plus d'exemples ajoutes au prompt.
- `format="json"` force la sortie JSON native d'Ollama (evite les guillemets simples/texte
  parasite qui causaient ~15% des echecs).

Champs RCCM/IFU/telephone de l'attributaire ajoutes pour fiabiliser le rapprochement avec une
Entreprise inscrite (cf. api/scripts/extract_bulletin.py, `_find_entreprise_attributaire`) - un nom
seul se preterait a des correspondances approximatives (deux entreprises au nom proche), alors
qu'un RCCM ou un IFU identique est une preuve quasi certaine. Rarement presents dans le texte reel
d'un resultat DGCMEF, mais utilises en priorite sur le nom quand ils le sont.
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
demande de prix, resultat d'attribution, manifestation d'interet, appel a manifestation d'interet, avis a manifestation d'interet...) et extrait ses informations. Le texte peut aussi etre
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
  "entreprise_attributaire_rccm": string | null, // numero RCCM de l'attributaire, UNIQUEMENT si explicitement ecrit dans le texte
  "entreprise_attributaire_ifu": string | null,  // numero IFU (identifiant financier unique) de l'attributaire, UNIQUEMENT si explicitement ecrit
  "entreprise_attributaire_telephone": string | null, // telephone de l'attributaire, UNIQUEMENT si explicitement ecrit
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

"entreprise_attributaire_rccm", "entreprise_attributaire_ifu" et "entreprise_attributaire_telephone"
ne sont presque jamais presents dans le texte d'un resultat (le nom seul suffit generalement) -
laisse-les a null par defaut, ne les remplis QUE si le numero exact apparait litteralement dans le
texte a cote du nom de l'attributaire. Ne confonds jamais un numero de reference de marche
(N°2026-xxx/...) avec un RCCM ou un IFU.

Si le texte ne decrit aucun avis de marche exploitable, reponds avec un tableau vide : []
Ne devine jamais une valeur (organisme, montant, date...) qui n'est pas explicitement dans le texte."""

SYSTEM_PROMPT_RESULTAT = """Tu extrais un RESULTAT D'ATTRIBUTION de marche public pour le Burkina \
Faso, a partir d'un extrait du bulletin "Quotidien des marches publics" (DGCMEF). Ce texte a deja \
ete identifie AVEC CERTITUDE comme un resultat (attributaire designe, marche declare non \
conforme, resultat provisoire/definitif...) - tu n'as PAS a classifier le type d'avis, uniquement \
a en extraire les informations.

Reponds UNIQUEMENT avec un tableau JSON valide (aucun texte avant/apres, aucun bloc markdown \
```json), ou chaque element respecte exactement ce schema :

{
  "organisme": string,              // autorite contractante / organisme emetteur
  "objet": string,                  // objet du marche concerne, resume en une phrase
  "type_procedure": string | null,  // ex. "demande de prix", "appel d'offres ouvert"
  "montant_min": number | null,     // montant en FCFA si mentionne
  "montant_max": number | null,
  "date_avis": string | null,       // date pertinente (attribution, deliberation...), ISO 8601 AAAA-MM-JJ
  "entreprise_attributaire_nom": string | null,  // nom de l'entreprise designee attributaire, si mentionne
  "entreprise_attributaire_rccm": string | null, // numero RCCM de l'attributaire, UNIQUEMENT si explicitement ecrit
  "entreprise_attributaire_ifu": string | null,  // numero IFU de l'attributaire, UNIQUEMENT si explicitement ecrit
  "entreprise_attributaire_telephone": string | null, // telephone de l'attributaire, UNIQUEMENT si explicitement ecrit
  "montant_attribue": number | null  // montant du marche attribue, en FCFA
}

"date_avis" doit etre soit une vraie date (jour/mois/annee explicites dans le texte), soit null.
Ne mets JAMAIS "non specifiee", une annee seule, ou un numero de reference/RCCM/IFU a la place
d'une date - dans ces cas, mets null.

"montant_attribue"/"montant_min"/"montant_max" doivent etre des nombres en FCFA, jamais un numero
de telephone ou une reference.

"entreprise_attributaire_rccm", "entreprise_attributaire_ifu" et "entreprise_attributaire_telephone"
ne sont presque jamais presents dans le texte d'un resultat (le nom seul suffit generalement) -
laisse-les a null par defaut, ne les remplis QUE si le numero exact apparait litteralement dans le
texte a cote du nom de l'attributaire. Ne confonds jamais un numero de reference de marche
(N°2026-xxx/...) avec un RCCM ou un IFU.

Le texte peut contenir, en plus du/des resultat(s) reel(s), du bruit residuel (ligne de tableau
isolee, numero de classement, fragment sans rapport) - INCLUS DANS LE MEME TEXTE qu'un vrai
resultat, donc jamais filtre en amont. N'invente jamais un element pour ce bruit et ne l'inclus
pas dans le tableau : seuls les VRAIS resultats d'attribution (avec au moins un organisme et un
objet reels) doivent y figurer. Le tableau peut donc contenir zero, un ou plusieurs elements.

Si le texte ne decrit en realite aucun resultat exploitable malgre l'identification prealable,
reponds avec un tableau vide : []
Ne devine jamais une valeur qui n'est pas explicitement dans le texte."""

SYSTEM_PROMPT_APPEL_OFFRE = """Tu extrais un AVIS D'APPEL D'OFFRES / DEMANDE DE PRIX / \
MANIFESTATION D'INTERET (nouvelle opportunite a soumissionner) pour le Burkina Faso, a partir \
d'un extrait du bulletin "Quotidien des marches publics" (DGCMEF). Ce texte a deja ete identifie \
AVEC CERTITUDE comme un nouvel avis (jamais un resultat deja attribue) - tu n'as PAS a classifier \
le type d'avis, uniquement a en extraire les informations.

Reponds UNIQUEMENT avec un tableau JSON valide (aucun texte avant/apres, aucun bloc markdown \
```json), ou chaque element respecte exactement ce schema :

{
  "organisme": string,              // autorite contractante / organisme emetteur
  "objet": string,                  // objet du marche, resume en une phrase
  "type_procedure": string | null,  // ex. "demande de prix", "appel d'offres ouvert"
  "montant_min": number | null,     // montant previsionnel en FCFA si mentionne
  "montant_max": number | null,
  "date_avis": string | null        // date pertinente (publication, ouverture des plis...), ISO 8601 AAAA-MM-JJ
}

"date_avis" doit etre soit une vraie date (jour/mois/annee explicites dans le texte), soit null.
Ne mets JAMAIS "non specifiee", une annee seule, ou un numero de reference a la place d'une date -
dans ces cas, mets null.

"montant_min"/"montant_max" doivent etre des nombres en FCFA, jamais un numero de telephone ou
une reference de marche.

Le texte peut contenir, en plus du/des avis reel(s), du bruit residuel (ligne de tableau isolee,
numero de classement, fragment sans rapport) - INCLUS DANS LE MEME TEXTE qu'un vrai avis, donc
jamais filtre en amont. N'invente jamais un element pour ce bruit et ne l'inclus pas dans le
tableau : seuls les VRAIS avis (avec au moins un organisme et un objet reels) doivent y figurer.
Le tableau peut donc contenir zero, un ou plusieurs elements.

Si le texte ne decrit en realite aucun avis exploitable malgre l'identification prealable,
reponds avec un tableau vide : []
Ne devine jamais une valeur qui n'est pas explicitement dans le texte."""

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
    entreprise_attributaire_rccm: str | None = None
    entreprise_attributaire_ifu: str | None = None
    entreprise_attributaire_telephone: str | None = None
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


def _deballer_json(texte_json: str) -> list[dict]:
    """Deballage commun aux 3 schemas d'extraction (generique/resultat/appel_offre) - purement
    structurel (liste de dicts bruts, pas encore valides contre un modele Pydantic precis)."""
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
    return [item for item in data if isinstance(item, dict)]


def _valider_avis(texte_json: str) -> list[AvisExtrait]:
    """Validation pour le prompt GENERIQUE (extraire_avis) - le LLM fournit lui-meme `type_avis`,
    normalise depuis ses synonymes reels observes avant validation."""
    return [AvisExtrait.model_validate(_normaliser_type_avis(item)) for item in _deballer_json(texte_json)]


def _valider_avis_resultat(texte_json: str) -> list[AvisExtrait]:
    """Validation pour le prompt RESULTAT (extraire_resultat) - `type_avis` n'est pas demande au
    LLM (deja connu, cf. docstring de module), impose directement ici."""
    return [AvisExtrait.model_validate({**item, "type_avis": "resultat"}) for item in _deballer_json(texte_json)]


def _valider_avis_appel_offre(texte_json: str) -> list[AvisExtrait]:
    """Symetrique de `_valider_avis_resultat` pour le prompt APPEL_OFFRE (extraire_appel_offre)."""
    return [AvisExtrait.model_validate({**item, "type_avis": "appel_offre"}) for item in _deballer_json(texte_json)]


def _extraire(texte_section: str, system_prompt: str, valider) -> list[AvisExtrait]:
    """Logique commune aux 3 fonctions d'extraction publiques : meme structure prompt + retry
    corrective, seuls le prompt systeme et le validateur (schema attendu) different. Retourne une
    liste (eventuellement vide). Retente une fois si la premiere reponse n'est pas un JSON valide ;
    leve `ExtractionEchouee` si la seconde tentative echoue aussi."""
    prompt = f"Texte du bulletin :\n\n{texte_section}"
    response = call_llm(TASK, messages=[{"role": "user", "content": prompt}], system=system_prompt, format="json")
    texte_reponse = _extraire_texte_reponse(response)

    try:
        return valider(texte_reponse)
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
            TASK, messages=[{"role": "user", "content": prompt_retry}], system=system_prompt, format="json"
        )
        texte_reponse_retry = _extraire_texte_reponse(response_retry)

        try:
            return valider(texte_reponse_retry)
        except (json.JSONDecodeError, ValidationError) as seconde_erreur:
            raise ExtractionEchouee(
                f"Extraction d'avis invalide apres une tentative de correction : {seconde_erreur}"
            ) from seconde_erreur


def extraire_avis(texte_section: str) -> list[AvisExtrait]:
    """Extrait les avis de marche presents dans `texte_section` (un groupe de chunks d'un meme
    `section_title`), en laissant le LLM classifier lui-meme le type - prompt de repli pour les
    sections ou `api/scripts/extract_bulletin._detecter_type_avis` ne peut pas trancher avec
    certitude (marqueurs des deux types presents, ou aucun)."""
    return _extraire(texte_section, SYSTEM_PROMPT, _valider_avis)


def extraire_resultat(texte_section: str) -> list[AvisExtrait]:
    """Comme `extraire_avis`, mais pour une section deja identifiee AVEC CERTITUDE comme un
    resultat (cf. `api/scripts/extract_bulletin._detecter_type_avis`) - prompt/schema restreints
    aux seuls champs pertinents pour un resultat, le LLM n'a plus a classifier le type ni a se
    demander s'il doit remplir des champs d'appel d'offre qui n'ont pas de sens ici."""
    return _extraire(texte_section, SYSTEM_PROMPT_RESULTAT, _valider_avis_resultat)


def extraire_appel_offre(texte_section: str) -> list[AvisExtrait]:
    """Symetrique de `extraire_resultat`, pour une section deja identifiee comme un nouvel avis
    (appel d'offres/demande de prix/manifestation d'interet) - schema encore plus restreint (pas
    de champs attributaire, denues de sens pour une nouvelle opportunite pas encore attribuee)."""
    return _extraire(texte_section, SYSTEM_PROMPT_APPEL_OFFRE, _valider_avis_appel_offre)
