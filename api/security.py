"""Hachage de mot de passe et JWT (access/refresh), equivalent de SIMPLE_JWT + passlib cote Django.

schemes=["django_pbkdf2_sha256", "bcrypt"] : les utilisateurs migres depuis db.sqlite3 ont un mot
de passe hache au format PBKDF2 de Django (pbkdf2_sha256$...) - passlib le lit nativement via ce
hasher, donc ils continuent de se connecter sans reinitialisation. Les nouvelles inscriptions sont
hachees en bcrypt (deprecated="auto" re-hache en bcrypt au prochain login reussi d'un compte migre).
"""

import base64
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.models.token_blacklist import RefreshTokenBlacklist
from api.models.utilisateur import Utilisateur

pwd_context = CryptContext(schemes=["bcrypt", "django_pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def validate_password_strength(password: str, email: str | None = None) -> list[str]:
    """Sous-ensemble pragmatique des validateurs Django (AUTH_PASSWORD_VALIDATORS) : longueur
    minimale, pas entierement numerique, pas trop proche de l'email. Retourne la liste des
    messages d'erreur (vide si le mot de passe est acceptable)."""
    errors = []
    if len(password) < 8:
        errors.append("Ce mot de passe est trop court. Il doit contenir au minimum 8 caractères.")
    if password.isdigit():
        errors.append("Ce mot de passe est entièrement numérique.")
    if email and email.split("@")[0].lower() in password.lower():
        errors.append("Le mot de passe est trop similaire à l'email.")
    return errors


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(user_id: int, token_type: str, lifetime: timedelta) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    payload = {
        "user_id": user_id,
        "token_type": token_type,
        "iat": now,
        "exp": now + lifetime,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def create_access_token(user_id: int) -> str:
    token, _ = _create_token(user_id, "access", timedelta(minutes=settings.access_token_lifetime_minutes))
    return token


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """Retourne (token, jti) - le jti est necessaire pour blacklister ce refresh token au logout
    ou lors de sa rotation (BLACKLIST_AFTER_ROTATION, meme comportement que simplejwt)."""
    return _create_token(user_id, "refresh", timedelta(days=settings.refresh_token_lifetime_days))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide ou expire") from exc


def revoke_refresh_token(db: Session, jti: str) -> None:
    if is_refresh_token_revoked(db, jti):
        return
    db.add(RefreshTokenBlacklist(jti=jti))
    db.commit()


def is_refresh_token_revoked(db: Session, jti: str) -> bool:
    return db.scalar(select(RefreshTokenBlacklist).where(RefreshTokenBlacklist.jti == jti)) is not None


def create_uid_token(user_id: int, purpose: str, lifetime: timedelta) -> tuple[str, str]:
    """Equivalent du couple (uidb64, token)  (urlsafe_base64_encode +
    default_token_generator), utilise pour les liens de reinitialisation de mot de passe et de
    verification d'email - stateless, pas de stockage en base."""
    uidb64 = base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip("=")
    token, _ = _create_token(user_id, purpose, lifetime)
    return uidb64, token


def verify_uid_token(uidb64: str, token: str, purpose: str) -> int | None:
    try:
        padding = "=" * (-len(uidb64) % 4)
        user_id = int(base64.urlsafe_b64decode(uidb64 + padding).decode())
    except (ValueError, UnicodeDecodeError):
        return None

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

    if payload.get("token_type") != purpose or payload.get("user_id") != user_id:
        return None
    return user_id


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Utilisateur:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise")

    payload = decode_token(credentials.credentials)
    if payload.get("token_type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Type de token invalide")

    user = db.get(Utilisateur, payload.get("user_id"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable ou inactif")
    return user
