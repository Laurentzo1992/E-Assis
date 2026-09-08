from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class RefreshTokenBlacklist(Base):
    """Equivalent de rest_framework_simplejwt.token_blacklist : jti revoques au logout, verifies
    a chaque rafraichissement de token."""

    __tablename__ = "refresh_token_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
