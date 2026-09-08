"""Prompts spécialisés pour l'extraction de résultats d'attribution de marchés publics.

Utilisé en FALLBACK CIBLÉ (Règle d'Or n°1) quand le parser géométrique / déterministe
ne parvient pas à extraire la totalité des lots ou des soumissionnaires dans des
tableaux non standards ou fragmentés sur plusieurs pages.

Retourne un schéma Pydantic strict et unifié avec le parser déterministe.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any, Sequence

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:
    class BaseModel:  # type: ignore
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        @classmethod
        def model_validate(cls, data):
            if isinstance(data, dict):
                # Gérer imbrication pour les lots et soumissionnaires si nécessaire
                return cls(**data)
            return data

    def Field(*args, default=None, default_factory=None, **kwargs):  # type: ignore
        if default_factory is not None:
            return default_factory()
        return default

    ValidationError = Exception  # type: ignore

logger = logging.getLogger(__name__)

TASK = "extraction"

SYSTEM_PROMPT_RESULTATS = """Tu es un expert en analyse des résultats de dépouillement et d'attribution \
de marchés publics au Burkina Faso (bulletin DGCMEF / Quotidien des marchés publics).

Ta mission est d'extraire fidèlement TOUTES les informations d'un résultat de délibération, \
de dépouillement ou de procès-verbal d'attribution.

Chaque résultat peut comporter un ou plusieurs LOTS.
Pour chaque LOT, tu dois lister TOUS les soumissionnaires mentionnés (l'attributaire/gagnant ET les \
entreprises écartées ou non retenues, avec leur motif d'élimination s'il est spécifié).

RÈGLES STRICTES :
1. "est_attributaire" doit valoir true UNIQUEMENT pour l'entreprise déclarée adjudicataire / retenue / attributaire du lot.
2. Pour les entreprises éliminées / rejetées / non conformes, "est_attributaire" est false et renseigne "motif_rejet".
3. Les montants doivent être des nombres entiers ou décimaux en FCFA (ex: 24500000), JAMAIS de texte dans le montant.
4. "ifu" et "rccm" ne doivent être renseignés que s'ils sont explicitement écrits dans le texte (sinon null). Ne jamais inventer.
5. Réponds UNIQUEMENT avec un objet JSON valide conforme au schéma demandé.
"""

PROMPT_SCHEMA_JSON = """{
  "autorite_contractante": string,       // Ministère, Mairie, Direction ou Institution émettrice
  "reference_dossier": string | null,    // N° du dossier, de la demande de prix ou de l'appel d'offres
  "objet": string,                       // Objet complet du marché
  "date_attribution": string | null,     // Date de la délibération (AAAA-MM-JJ) si mentionnée, sinon null
  "statut_deliberation": "ATTRIBUE" | "INFRUCTUEUX" | "ANNULE" | "PARTIEL",
  "lots": [
    {
      "numero_lot": string,              // "1", "2", ou "Lot unique"
      "intitule_lot": string | null,     // Description spécifique du lot
      "montant_estime": number | null,   // Montant prévisionnel si mentionné
      "statut_lot": "ATTRIBUE" | "INFRUCTUEUX" | "ANNULE" | "SANS_SUITE",
      "soumissionnaires": [
        {
          "nom_entreprise": string,      // Nom exact de l'entreprise ou du groupement
          "ifu": string | null,          // IFU si écrit dans le texte
          "rccm": string | null,         // RCCM si écrit dans le texte
          "est_attributaire": boolean,   // true si vainqueur du lot, false sinon
          "statut": "ATTRIBUTAIRE" | "ECARTE" | "RETENU_NON_ATTRIBUTAIRE",
          "rang_classement": number | null, // 1 pour le premier, 2 pour le second...
          "montant_lu": number | null,   // Montant lu à l'ouverture
          "montant_corrige": number | null, // Montant final proposé / retenu
          "delai_execution": string | null, // Délai (ex: "30 jours", "2 mois")
          "motif_rejet": string | null   // Motif si écarté (ex: "Dossier technique non conforme", "Prix excessif")
        }
      ]
    }
  ]
}"""


class SoumissionnaireExtractionSchema(BaseModel):
    nom_entreprise: str
    ifu: str | None = None
    rccm: str | None = None
    est_attributaire: bool = False
    statut: str = "ECARTE"
    rang_classement: int | None = None
    montant_lu: float | None = None
    montant_corrige: float | None = None
    delai_execution: str | None = None
    motif_rejet: str | None = None


class LotExtractionSchema(BaseModel):
    numero_lot: str = "1"
    intitule_lot: str | None = None
    montant_estime: float | None = None
    statut_lot: str = "ATTRIBUE"
    soumissionnaires: list[SoumissionnaireExtractionSchema] = Field(default_factory=list)


class ResultatExtractionSchema(BaseModel):
    autorite_contractante: str = "Autorité contractante non spécifiée"
    reference_dossier: str | None = None
    objet: str = "Objet du marché non spécifié"
    date_attribution: str | None = None
    statut_deliberation: str = "ATTRIBUE"
    lots: list[LotExtractionSchema] = Field(default_factory=list)


def _extraire_json_de_reponse(texte_reponse: str) -> str:
    """Extrait le bloc JSON propre d'une réponse textuelle ou markdown du LLM."""
    json_match = re.search(r"```json\s*\n(.*?)\n```", texte_reponse, re.DOTALL | re.IGNORECASE)
    if json_match:
        return json_match.group(1).strip()
    json_match = re.search(r"```\s*\n(.*?)\n```", texte_reponse, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    json_match = re.search(r"(\{.*\})", texte_reponse, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    return texte_reponse.strip()


def parse_llm_date(date_str: str | None) -> date | None:
    """Parse une date au format ISO AAAA-MM-JJ ou renvoie None en toute sécurité."""
    if not date_str:
        return None
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if not match:
        return None
    annee, mois, jour = match.groups()
    try:
        return date(int(annee), int(mois), int(jour))
    except ValueError:
        return None


def extraire_resultats_avec_llm(texte: str, *, client: Any = None) -> ResultatExtractionSchema | None:
    """Appel LLM ciblé en fallback pour structurer les résultats d'attribution récalcitrants."""
    from llm_service.llm_client import call_llm

    user_prompt = (
        f"Voici l'extrait du bulletin Quotidien des marchés publics présentant un résultat de marché :\n\n"
        f"```text\n{texte.strip()}\n```\n\n"
        f"Extrais les informations complètes au format JSON suivant :\n{PROMPT_SCHEMA_JSON}\n\n"
        f"Réponds UNIQUEMENT avec le JSON valide, sans texte additionnel."
    )

    try:
        response = call_llm(
            task=TASK,
            messages=[{"role": "user", "content": user_prompt}],
            system=SYSTEM_PROMPT_RESULTATS,
            client=client,
        )
        contenu = response.message.content or ""
        json_propre = _extraire_json_de_reponse(contenu)
        data = json.loads(json_propre)

        if isinstance(data, dict):
            if not data.get("autorite_contractante"):
                data["autorite_contractante"] = "Autorité contractante non spécifiée"
            if not data.get("objet"):
                data["objet"] = "Objet du marché non spécifié"

        return ResultatExtractionSchema.model_validate(data)
    except Exception as exc:
        logger.error("Échec du fallback LLM pour l'extraction de résultat : %s", exc)
        return None
