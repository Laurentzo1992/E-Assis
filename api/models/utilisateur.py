import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.entreprise import Entreprise


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    repnom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repprenom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notifications_actives: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    activation_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    activation_token_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # use_alter : reference circulaire avec Entreprise.owner_id (-> utilisateurs.id) - la FK est
    # ajoutee via ALTER TABLE apres creation des deux tables, pas dans le CREATE TABLE initial.
    active_entreprise_id: Mapped[int | None] = mapped_column(
        ForeignKey("entreprises.id", ondelete="SET NULL", use_alter=True, name="fk_utilisateurs_active_entreprise"),
        nullable=True,
    )

    date_joined: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owned_entreprises: Mapped[list["Entreprise"]] = relationship(
        back_populates="owner", foreign_keys="Entreprise.owner_id"
    )
    active_entreprise: Mapped["Entreprise | None"] = relationship(foreign_keys=[active_entreprise_id])

    def __str__(self) -> str:
        return self.email
