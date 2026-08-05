"""Modeles de l'app 'backend' Django : publications de marches publics, procedures, resultats.

AppelOffre et Resultat reproduisent l'heritage multi-table Django (marche_ptr) : leur PK est
directement la FK vers marches.id, sans polymorphisme Python (inutile ici, seule la forme des
tables doit correspondre pour la parite de schema demandee).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.entreprise import Domaine, Entreprise


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    titre: Mapped[str] = mapped_column(String(255))
    numero: Mapped[str] = mapped_column(String(100))
    date_publication: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    type_publication: Mapped[str | None] = mapped_column(String(100), nullable=True)

    domaines: Mapped[list["Domaine"]] = relationship(secondary="publication_domaines", viewonly=True)


class TypeProcedure(Base):
    __tablename__ = "types_procedure"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PublicationDomaine(Base):
    __tablename__ = "publication_domaines"
    __table_args__ = (UniqueConstraint("publication_id", "domaine_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"))
    domaine_id: Mapped[int] = mapped_column(ForeignKey("domaines.id", ondelete="CASCADE"))


class Marche(Base):
    __tablename__ = "marches"

    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"))
    type_procedure_id: Mapped[int | None] = mapped_column(
        ForeignKey("types_procedure.id", ondelete="SET NULL"), nullable=True
    )
    ministere: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    objet: Mapped[str] = mapped_column(Text)
    budget_min: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    page_number: Mapped[int | None] = mapped_column(nullable=True)

    publication: Mapped[Publication] = relationship()
    type_procedure: Mapped["TypeProcedure | None"] = relationship()
    lots: Mapped[list["Lot"]] = relationship(back_populates="marche")


class AppelOffre(Base):
    __tablename__ = "appels_offre"

    marche_id: Mapped[int] = mapped_column(ForeignKey("marches.id", ondelete="CASCADE"), primary_key=True)
    dateDepot: Mapped[date | None] = mapped_column(Date, nullable=True)
    referenceDossier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lieuDepot: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditionsParticipation: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteresSelection: Mapped[str | None] = mapped_column(Text, nullable=True)
    cautionnement: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    dureeValiditeOffres: Mapped[str | None] = mapped_column(String(255), nullable=True)

    marche: Mapped[Marche] = relationship()


class Resultat(Base):
    __tablename__ = "resultats"

    marche_id: Mapped[int] = mapped_column(ForeignKey("marches.id", ondelete="CASCADE"), primary_key=True)
    date_attribution: Mapped[date | None] = mapped_column(Date, nullable=True)
    entreprise_attributaire_id: Mapped[int | None] = mapped_column(
        ForeignKey("entreprises.id", ondelete="SET NULL"), nullable=True
    )
    montant_attribue: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    reference_decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nombre_offres_recues: Mapped[int | None] = mapped_column(nullable=True)
    delai_execution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    motif_rejet_autres_offres: Mapped[str | None] = mapped_column(Text, nullable=True)

    marche: Mapped[Marche] = relationship()
    entreprise_attributaire: Mapped["Entreprise | None"] = relationship()


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    marche_id: Mapped[int] = mapped_column(ForeignKey("marches.id", ondelete="CASCADE"))
    numero_lot: Mapped[int] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    montant: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    marche: Mapped[Marche] = relationship(back_populates="lots")


class Alerte(Base):
    __tablename__ = "alertes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entreprise_id: Mapped[int] = mapped_column(ForeignKey("entreprises.id", ondelete="CASCADE"))
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"))
    marche_id: Mapped[int | None] = mapped_column(ForeignKey("marches.id", ondelete="CASCADE"), nullable=True)
    type_alerte: Mapped[str] = mapped_column(String(50))
    date_alerte: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contenu_alerte: Mapped[str] = mapped_column(Text)
    canal_alerte: Mapped[str] = mapped_column(String(30))

    entreprise: Mapped["Entreprise"] = relationship()
    publication: Mapped[Publication] = relationship()
    marche: Mapped["Marche | None"] = relationship()
