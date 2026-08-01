from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.utilisateur import Utilisateur


class Domaine(Base):
    __tablename__ = "domaines"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SecteurActivite(Base):
    __tablename__ = "secteurs_activite"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Entreprise(Base):
    __tablename__ = "entreprises"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(255))
    numero_identification: Mapped[str] = mapped_column(String(100), unique=True)
    siret: Mapped[str] = mapped_column(String(20), unique=True)
    adresse: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_creation: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repnom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repprenom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rccm: Mapped[str | None] = mapped_column(String(15), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id", ondelete="CASCADE"))

    owner: Mapped["Utilisateur"] = relationship(back_populates="owned_entreprises", foreign_keys=[owner_id])
    domaines: Mapped[list[Domaine]] = relationship(secondary="entreprise_domaines", viewonly=True)
    secteurs: Mapped[list[SecteurActivite]] = relationship(secondary="entreprise_secteurs", viewonly=True)


class EntrepriseDomaine(Base):
    __tablename__ = "entreprise_domaines"
    __table_args__ = (UniqueConstraint("entreprise_id", "domaine_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entreprise_id: Mapped[int] = mapped_column(ForeignKey("entreprises.id", ondelete="CASCADE"))
    domaine_id: Mapped[int] = mapped_column(ForeignKey("domaines.id", ondelete="CASCADE"))


class EntrepriseSecteur(Base):
    __tablename__ = "entreprise_secteurs"
    __table_args__ = (UniqueConstraint("entreprise_id", "secteur_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entreprise_id: Mapped[int] = mapped_column(ForeignKey("entreprises.id", ondelete="CASCADE"))
    secteur_id: Mapped[int] = mapped_column(ForeignKey("secteurs_activite.id", ondelete="CASCADE"))
