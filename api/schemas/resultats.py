"""Schémas Pydantic pour le module des résultats d'attribution de marchés publics.

Conformément à la Charte d'Ingénierie (Règles n°2, n°3 et n°5) :
- Traçabilité et auditabilité de la décision (score_matching, methode_matching, motif_rejet).
- Prise en compte des structures multi-lots et des soumissionnaires.
- Modération et arbitrage des statuts A_VERIFIER.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# --- Soumissionnaires & Lots ---


class SoumissionnaireResultatResponse(BaseModel):
    id: int
    lot_resultat_id: int
    entreprise_id: int | None = None
    nom_entreprise_brut: str
    nom_entreprise_normalise: str | None = None
    ifu_extrait: str | None = None
    rccm_extrait: str | None = None
    statut: str
    est_attributaire: bool
    rang_classement: int | None = None
    montant_lu: Decimal | None = None
    montant_corrige: Decimal | None = None
    delai_execution: str | None = None
    motif_rejet: str | None = None
    score_matching: float | None = None
    methode_matching: str | None = None
    statut_reconciliation: str

    model_config = {"from_attributes": True}


class LotResultatResponse(BaseModel):
    id: int
    resultat_attribution_id: int
    numero_lot: str
    intitule_lot: str | None = None
    montant_estime: Decimal | None = None
    statut_lot: str
    soumissionnaires: list[SoumissionnaireResultatResponse] = []

    model_config = {"from_attributes": True}


# --- Résultat d'attribution (En-tête & Détails) ---


class ResultatAttributionResponse(BaseModel):
    id: int
    publication_id: int | None = None
    marche_id: int | None = None
    bulletin_numero: str | None = None
    page_source: int | None = None
    autorite_contractante: str
    reference_dossier: str | None = None
    objet: str
    date_attribution: date | None = None
    date_extraction: datetime
    statut_deliberation: str
    raw_source_snippet: str | None = None
    lots: list[LotResultatResponse] = []

    model_config = {"from_attributes": True}


class ResultatEntrepriseItem(BaseModel):
    """Synthèse d'un résultat pour une entreprise cliente (Victoire ou REX)."""

    soumissionnaire_id: int
    resultat_id: int
    publication_id: int | None = None
    bulletin_numero: str | None = None
    page_source: int | None = None
    autorite_contractante: str
    reference_dossier: str | None = None
    objet: str
    numero_lot: str
    intitule_lot: str | None = None
    est_attributaire: bool
    statut: str
    rang_classement: int | None = None
    montant_attribue_ou_soumis: Decimal | None = None
    delai_execution: str | None = None
    motif_rejet: str | None = None
    nom_attributaire_retenu: str | None = None
    montant_attributaire_retenu: Decimal | None = None
    score_reconciliation: float | None = None
    statut_reconciliation: str


# --- Alertes reçues sur les résultats ---


class AlerteResultatResponse(BaseModel):
    id: int
    entreprise_id: int
    soumissionnaire_resultat_id: int
    canal_alerte: str
    type_notification: str
    contenu_alerte: str
    date_envoi: datetime
    statut_envoi: str
    message_hash: str

    model_config = {"from_attributes": True}


# --- Modération Administrateur / Arbitrage Règle d'Or n°2 ---


class SoumissionnaireAVerifierResponse(BaseModel):
    id: int
    nom_entreprise_brut: str
    nom_entreprise_normalise: str | None = None
    ifu_extrait: str | None = None
    rccm_extrait: str | None = None
    score_matching: float | None = None
    methode_matching: str | None = None
    bulletin_numero: str | None = None
    page_source: int | None = None
    autorite_contractante: str
    objet: str
    numero_lot: str
    est_attributaire: bool
    montant: Decimal | None = None
    candidats_reconcilies_possibles: list[dict[str, Any]] = []


class ReconcilierSoumissionnaireRequest(BaseModel):
    """Arbitrage manuel pour valider ou rejeter un candidat en doute (A_VERIFIER)."""

    action: str = Field(..., description="'VALIDER' pour rattacher à entreprise_id, 'REJETER' pour annuler")
    entreprise_id: int | None = Field(None, description="ID de l'entreprise cible si action='VALIDER'")
    emettre_alerte: bool = Field(True, description="Déclencher la notification immédiatement si validé")


class ReconcilierSoumissionnaireResponse(BaseModel):
    status: str
    soumissionnaire_id: int
    statut_reconciliation: str
    entreprise_id: int | None = None
    alerte_emise: bool = False
    detail: str
