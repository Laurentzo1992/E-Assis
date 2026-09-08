"""Modèles SQLAlchemy pour les résultats d'attribution de marchés publics.

Conformément à la Charte d'Ingénierie (Règles n°2, n°3 et n°5) :
- Traçabilité complète de la source (bulletin_numero, page_source, extrait_brut)
- Prise en compte des structures multi-lots (un marché peut comporter N lots)
- Suivi de tous les soumissionnaires par lot (attributaires ET écartés avec motif d'élimination)
- Journalisation idempotente des alertes de résultats (AlerteResultat)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.backend import Marche, Publication
    from api.models.entreprise import Entreprise


class ResultatAttribution(Base):
    """En-tête d'un résultat d'attribution / dépouillement dans un bulletin.

    Peut être relié à une Publication existante (si le bulletin est référencé)
    ou directement à un Marché (s'il correspond à un appel d'offres déjà répertorié).
    """

    __tablename__ = "resultats_attribution"

    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int | None] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    marche_id: Mapped[int | None] = mapped_column(
        ForeignKey("marches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Métadonnées et traçabilité source
    bulletin_numero: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    page_source: Mapped[int | None] = mapped_column(Integer, nullable=True)
    autorite_contractante: Mapped[str] = mapped_column(String(255), index=True)
    reference_dossier: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    objet: Mapped[str] = mapped_column(Text)
    date_attribution: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_extraction: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    statut_deliberation: Mapped[str] = mapped_column(
        String(50), default="ATTRIBUE", server_default="ATTRIBUE"
    )  # ATTRIBUE, INFRUCTUEUX, ANNULE, PARTIEL
    raw_source_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    publication: Mapped[Publication | None] = relationship()
    marche: Mapped[Marche | None] = relationship()
    lots: Mapped[list[LotResultat]] = relationship(
        back_populates="resultat_attribution", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_res_attrib_dossier_bulletin", "bulletin_numero", "reference_dossier"),
    )

    def __str__(self) -> str:
        return f"Résultat {self.reference_dossier or self.id} - {self.autorite_contractante}"


class LotResultat(Base):
    """Lot individuel au sein d'une délibération de marché."""

    __tablename__ = "lots_resultats"

    id: Mapped[int] = mapped_column(primary_key=True)
    resultat_attribution_id: Mapped[int] = mapped_column(
        ForeignKey("resultats_attribution.id", ondelete="CASCADE"), index=True
    )
    numero_lot: Mapped[str] = mapped_column(String(50), default="1", server_default="1")
    intitule_lot: Mapped[str | None] = mapped_column(Text, nullable=True)
    montant_estime: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    statut_lot: Mapped[str] = mapped_column(
        String(50), default="ATTRIBUE", server_default="ATTRIBUE"
    )  # ATTRIBUE, INFRUCTUEUX, ANNULE, SANS_SUITE

    resultat_attribution: Mapped[ResultatAttribution] = relationship(back_populates="lots")
    soumissionnaires: Mapped[list[SoumissionnaireResultat]] = relationship(
        back_populates="lot_resultat", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("resultat_attribution_id", "numero_lot", name="uq_lot_par_resultat"),
    )

    def __str__(self) -> str:
        return f"Lot {self.numero_lot} ({self.statut_lot}) - Résultat #{self.resultat_attribution_id}"


class SoumissionnaireResultat(Base):
    """Offre et décision pour une entreprise candidate sur un lot donné."""

    __tablename__ = "soumissionnaires_resultats"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_resultat_id: Mapped[int] = mapped_column(
        ForeignKey("lots_resultats.id", ondelete="CASCADE"), index=True
    )

    # Entreprise réconciliée (si inscrite dans notre plateforme)
    entreprise_id: Mapped[int | None] = mapped_column(
        ForeignKey("entreprises.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Identité extraite brute du bulletin
    nom_entreprise_brut: Mapped[str] = mapped_column(String(255), index=True)
    nom_entreprise_normalise: Mapped[str | None] = mapped_column(String(255), index=True)
    ifu_extrait: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    rccm_extrait: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Décision et classement
    statut: Mapped[str] = mapped_column(
        String(30), index=True
    )  # ATTRIBUTAIRE, ECARTE, RETENU_NON_ATTRIBUTAIRE
    est_attributaire: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    rang_classement: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Montants & conditions
    montant_lu: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    montant_corrige: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    delai_execution: Mapped[str | None] = mapped_column(String(100), nullable=True)
    motif_rejet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit réconciliation (Règle n°2 & n°5)
    score_matching: Mapped[float | None] = mapped_column(Float, nullable=True)
    methode_matching: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # IFU_EXACT, RCCM_EXACT, CANONICAL_EXACT, TRIGRAMME, MANUEL
    statut_reconciliation: Mapped[str] = mapped_column(
        String(30), default="NON_ASSIGNE", server_default="NON_ASSIGNE"
    )  # EXACT, PROBABLE, A_VERIFIER, NON_ASSIGNE

    lot_resultat: Mapped[LotResultat] = relationship(back_populates="soumissionnaires")
    entreprise: Mapped[Entreprise | None] = relationship()

    def __str__(self) -> str:
        decision = "GAGNANT" if self.est_attributaire else "ECARTE"
        return f"{self.nom_entreprise_brut} ({decision}) - Lot #{self.lot_resultat_id}"


class AlerteResultat(Base):
    """Traçabilité et déduplication des alertes émises sur les résultats (Règle d'Or n°3)."""

    __tablename__ = "alertes_resultats"

    id: Mapped[int] = mapped_column(primary_key=True)
    entreprise_id: Mapped[int] = mapped_column(
        ForeignKey("entreprises.id", ondelete="CASCADE"), index=True
    )
    soumissionnaire_resultat_id: Mapped[int] = mapped_column(
        ForeignKey("soumissionnaires_resultats.id", ondelete="CASCADE"), index=True
    )
    canal_alerte: Mapped[str] = mapped_column(String(30))  # whatsapp, email, whatsapp+email
    type_notification: Mapped[str] = mapped_column(
        String(50)
    )  # ATTRIBUTION_VICTOIRE, ATTRIBUTION_ECHEC
    contenu_alerte: Mapped[str] = mapped_column(Text)
    date_envoi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    statut_envoi: Mapped[str] = mapped_column(
        String(30), default="SENT", server_default="SENT"
    )  # SENT, FAILED, PENDING
    message_hash: Mapped[str] = mapped_column(String(64), index=True)

    entreprise: Mapped[Entreprise] = relationship()
    soumissionnaire_resultat: Mapped[SoumissionnaireResultat] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "entreprise_id",
            "soumissionnaire_resultat_id",
            "type_notification",
            name="uq_alerte_resultat_par_soumissionnaire",
        ),
    )

    def __str__(self) -> str:
        return f"Alerte {self.type_notification} -> Entreprise #{self.entreprise_id} ({self.statut_envoi})"
