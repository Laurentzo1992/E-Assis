"""Schemas Pydantic pour l'auth.

Les corps de requete (Register/Login/...) sont volontairement types en `str | None` sans
validation Pydantic stricte (pas de EmailStr, pas de champs requis) : DRF renvoie ses erreurs de
validation comme un dict `{"champ": ["message"]}` non enveloppe, une forme que l'auto-422 de
FastAPI/Pydantic ne produit pas. Les routers valident donc ces champs a la main et renvoient une
JSONResponse dans le meme format que l'API DRF existante (compatibilite stricte avec
frontend), plutot que de laisser Pydantic rejeter la requete avec sa propre forme d'erreur.
"""

from datetime import datetime

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    repnom: str | None = None
    repprenom: str | None = None


class LoginRequest(BaseModel):
    email: str | None = None
    password: str | None = None


class TokenPairResponse(BaseModel):
    access: str
    refresh: str


class TokenRefreshRequest(BaseModel):
    refresh: str | None = None


class TokenRefreshResponse(BaseModel):
    access: str
    refresh: str


class ProfileResponse(BaseModel):
    id: int
    email: str
    repnom: str | None
    repprenom: str | None
    telephone: str | None
    notifications_actives: bool
    langue: str

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    repnom: str | None = None
    repprenom: str | None = None
    telephone: str | None = None
    notifications_actives: bool | None = None
    langue: str | None = None


class GoogleLoginRequest(BaseModel):
    id_token: str | None = None


class GoogleUserSummary(BaseModel):
    id: int
    email: str
    repnom: str | None
    repprenom: str | None


class GoogleLoginResponse(BaseModel):
    refresh: str
    access: str
    user: GoogleUserSummary


class ChangePasswordRequest(BaseModel):
    old_password: str | None = None
    new_password: str | None = None


class ResetPasswordRequestRequest(BaseModel):
    email: str | None = None


class ResetPasswordConfirmRequest(BaseModel):
    uidb64: str | None = None
    token: str | None = None
    new_password: str | None = None


class UtilisateurSummary(BaseModel):
    id: int
    email: str
    repnom: str | None
    repprenom: str | None
    is_active: bool
    is_staff: bool
    date_joined: datetime
    last_login: datetime | None

    model_config = {"from_attributes": True}
