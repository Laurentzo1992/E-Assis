"""Abonnement annuel par entreprise : essai gratuit a la creation, puis paiement pour continuer.

Un seul `Abonnement` par entreprise (cf. contrainte unique sur entreprise_id) - pas d'historique de
plans multiples, juste un statut courant et ses dates de validite. Chaque paiement reussi prolonge
`date_fin_abonnement` d'un an a partir de la date la plus tardive entre "maintenant" et l'ancienne
date de fin (un renouvellement anticipe n'est jamais perdu).
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.entreprise import Entreprise

# "essai" : periode d'essai gratuite en cours (date_fin_essai dans le futur).
# "actif" : abonnement paye en cours (date_fin_abonnement dans le futur).
# "expire" : essai ou abonnement termine, aucun paiement en attente - fonctionnalites bloquees.
STATUTS_ABONNEMENT = ("essai", "actif", "expire")

STATUTS_PAIEMENT = ("en_attente", "reussi", "echoue")


class Abonnement(Base):
    __tablename__ = "abonnements"

    id: Mapped[int] = mapped_column(primary_key=True)
    entreprise_id: Mapped[int] = mapped_column(
        ForeignKey("entreprises.id", ondelete="CASCADE"), unique=True
    )
    statut: Mapped[str] = mapped_column(String(20), default="essai")
    date_debut_essai: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_fin_essai: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_fin_abonnement: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entreprise: Mapped["Entreprise"] = relationship()
    paiements: Mapped[list["Paiement"]] = relationship(back_populates="abonnement", order_by="Paiement.date_creation.desc()")

    def __str__(self) -> str:
        return f"Abonnement {self.entreprise} ({self.statut})"


class Paiement(Base):
    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(primary_key=True)
    abonnement_id: Mapped[int] = mapped_column(ForeignKey("abonnements.id", ondelete="CASCADE"))
    # Reference generee par nous, envoyee au fournisseur comme transaction_id - sert de cle
    # d'idempotence : un webhook rejoue avec la meme reference ne credite jamais deux fois.
    reference: Mapped[str] = mapped_column(String(100), unique=True)
    reference_fournisseur: Mapped[str | None] = mapped_column(String(150), nullable=True)
    fournisseur: Mapped[str] = mapped_column(String(30))
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    devise: Mapped[str] = mapped_column(String(3), default="XOF")
    statut: Mapped[str] = mapped_column(String(20), default="en_attente")
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_confirmation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    abonnement: Mapped["Abonnement"] = relationship(back_populates="paiements")

    def __str__(self) -> str:
        return f"Paiement {self.reference} ({self.statut})"
