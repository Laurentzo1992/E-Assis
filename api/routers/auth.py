"""Routes d'authentification - reproduit exactement les chemins et formats de reponse de
authentication/urls.py + les deux routes /api/token/* de core/urls.py, verifies contre
frontend/src/services/auth.js et ActivateAccount.jsx (seule route reellement appelee cote
frontend pour l'activation : GET /api/auth/activate/{token}/).
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.email_utils import send_activation_email, send_password_reset_email
from api.models.utilisateur import Utilisateur
from api.schemas.auth import (
    ChangePasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordConfirmRequest,
    ResetPasswordRequestRequest,
    TokenPairResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from api.security import (
    create_access_token,
    create_refresh_token,
    create_uid_token,
    decode_token,
    get_current_user,
    hash_password,
    is_refresh_token_revoked,
    revoke_refresh_token,
    validate_password_strength,
    verify_password,
    verify_uid_token,
)

router = APIRouter()


def _issue_token_pair(db: Session, user: Utilisateur) -> dict:
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    access = create_access_token(user.id)
    refresh, _ = create_refresh_token(user.id)
    return {"access": access, "refresh": refresh}


# --- /api/token/ (TokenObtainPairView) et /api/token/refresh/ ------------------------------


@router.post("/api/token/", response_model=TokenPairResponse)
def token_obtain_pair(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(Utilisateur).where(Utilisateur.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password or "", user.password_hash):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "No active account found with the given credentials"},
        )
    return _issue_token_pair(db, user)


@router.post("/api/token/refresh/", response_model=TokenRefreshResponse)
def token_refresh(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    if not payload.refresh:
        return JSONResponse(status_code=400, content={"refresh": ["Ce champ est obligatoire."]})

    try:
        decoded = decode_token(payload.refresh)
    except Exception:
        return JSONResponse(
            status_code=401, content={"detail": "Token is invalid or expired", "code": "token_not_valid"}
        )

    if decoded.get("token_type") != "refresh" or is_refresh_token_revoked(db, decoded.get("jti", "")):
        return JSONResponse(
            status_code=401, content={"detail": "Token is invalid or expired", "code": "token_not_valid"}
        )

    # ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION : l'ancien refresh est revoque des qu'un
    # nouveau est emis, meme comportement que simplejwt.
    revoke_refresh_token(db, decoded["jti"])
    access = create_access_token(decoded["user_id"])
    new_refresh, _ = create_refresh_token(decoded["user_id"])
    return {"access": access, "refresh": new_refresh}


# --- /api/auth/register/ + /api/auth/activate/{token}/ -------------------------------------


@router.post("/api/auth/register/", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    errors: dict[str, list[str]] = {}
    if not payload.email:
        errors["email"] = ["Ce champ est obligatoire."]
    elif db.scalar(select(Utilisateur).where(Utilisateur.email == payload.email)):
        errors["email"] = ["Un compte avec cet email existe déjà."]
    if not payload.password:
        errors["password"] = ["Ce champ est obligatoire."]
    elif payload.email:
        password_errors = validate_password_strength(payload.password, payload.email)
        if password_errors:
            errors["password"] = password_errors

    if errors:
        return JSONResponse(status_code=400, content=errors)

    user = Utilisateur(
        email=payload.email,
        password_hash=hash_password(payload.password),
        repnom=payload.repnom or "",
        repprenom=payload.repprenom or "",
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    activation_link = f"{settings.frontend_domain}/verification/{user.activation_token}"
    send_activation_email(user.email, activation_link)

    return {"message": "Utilisateur créé. Vérifiez votre email pour activer votre compte."}


@router.get("/api/auth/activate/{token}/")
def activate_account(token: uuid.UUID, db: Session = Depends(get_db)):
    user = db.scalar(select(Utilisateur).where(Utilisateur.activation_token == token))
    if user is None:
        return JSONResponse(status_code=400, content={"error": "Lien invalide."})

    if user.is_active:
        return {"message": "Compte activé."}

    age = datetime.now(timezone.utc) - user.activation_token_created_at.replace(tzinfo=timezone.utc)
    if age.total_seconds() > settings.activation_token_lifetime_minutes * 60:
        return JSONResponse(status_code=400, content={"error": "Le lien d'activation a expiré."})

    user.is_active = True
    user.is_email_verified = True
    db.commit()
    return {"message": "Compte activé avec succès."}


# --- /api/auth/login/ -----------------------------------------------------------------------


@router.post("/api/auth/login/")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    if not payload.email or not payload.password:
        return JSONResponse(
            status_code=400, content={"non_field_errors": ['Doit inclure "email" et "password".']}
        )

    user = db.scalar(select(Utilisateur).where(Utilisateur.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        return JSONResponse(
            status_code=400,
            content={"non_field_errors": ["Impossible de se connecter avec les identifiants fournis."]},
        )

    return _issue_token_pair(db, user)


# --- /api/auth/profile/ ----------------------------------------------------------------------


@router.get("/api/auth/profile/", response_model=ProfileResponse)
def get_profile(current_user: Utilisateur = Depends(get_current_user)):
    return current_user


@router.put("/api/auth/profile/", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field in ("repnom", "repprenom", "telephone", "notifications_actives"):
        value = getattr(payload, field)
        if value is not None:
            setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


# --- /api/auth/google-login/ -----------------------------------------------------------------


@router.post("/api/auth/google-login/")
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    if not payload.id_token:
        return JSONResponse(status_code=400, content={"detail": "ID token manquant."})

    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Token Google invalide."})
    except Exception as exc:  # noqa: BLE001 - parite avec le comportement Django (exception generique -> 500)
        return JSONResponse(status_code=500, content={"detail": f"Une erreur est survenue: {exc}"})

    email = idinfo["email"]
    user = db.scalar(select(Utilisateur).where(Utilisateur.email == email))
    if user is None:
        user = Utilisateur(
            email=email,
            password_hash=hash_password(uuid.uuid4().hex),  # mot de passe inutilisable
            repnom=idinfo.get("family_name", ""),
            repprenom=idinfo.get("given_name", ""),
            is_email_verified=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    tokens = _issue_token_pair(db, user)
    return {
        **tokens,
        "user": {"id": user.id, "email": user.email, "repnom": user.repnom, "repprenom": user.repprenom},
    }


# --- /api/auth/change-password/ ---------------------------------------------------------------


@router.post("/api/auth/change-password/")
def change_password(
    payload: ChangePasswordRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password or "", current_user.password_hash):
        return JSONResponse(status_code=400, content={"old_password": ["Ancien mot de passe incorrect."]})

    password_errors = validate_password_strength(payload.new_password or "", current_user.email)
    if password_errors:
        return JSONResponse(status_code=400, content={"new_password": password_errors})

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Mot de passe changé avec succès."}


# --- /api/auth/reset-password-request/ + /api/auth/reset-password-confirm/ -------------------

_RESET_PURPOSE = "password_reset"
_RESET_LIFETIME = timedelta(hours=1)


@router.post("/api/auth/reset-password-request/")
def reset_password_request(payload: ResetPasswordRequestRequest, db: Session = Depends(get_db)):
    if not payload.email:
        return JSONResponse(status_code=400, content={"detail": "L'email est requis."})

    user = db.scalar(select(Utilisateur).where(Utilisateur.email == payload.email))
    if user is not None:
        uidb64, token = create_uid_token(user.id, _RESET_PURPOSE, _RESET_LIFETIME)
        reset_url = f"{settings.frontend_domain}/reset-password-confirm/{uidb64}/{token}/"
        user_name = f"{user.repprenom} {user.repnom}".strip() or user.email
        send_password_reset_email(user.email, user_name, reset_url)

    # Ne revele jamais si l'email existe ou non (meme comportement que la vue Django d'origine).
    return {"message": "Si votre adresse email est valide, un lien de réinitialisation vous a été envoyé."}


@router.post("/api/auth/reset-password-confirm/")
def reset_password_confirm(payload: ResetPasswordConfirmRequest, db: Session = Depends(get_db)):
    user_id = verify_uid_token(payload.uidb64 or "", payload.token or "", _RESET_PURPOSE)
    if user_id is None:
        return JSONResponse(
            status_code=400, content={"detail": "Le lien de réinitialisation est invalide ou a expiré."}
        )

    user = db.get(Utilisateur, user_id)
    if user is None:
        return JSONResponse(
            status_code=400, content={"detail": "Le lien de réinitialisation est invalide ou a expiré."}
        )

    password_errors = validate_password_strength(payload.new_password or "", user.email)
    if password_errors:
        return JSONResponse(status_code=400, content={"new_password": password_errors})

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Votre mot de passe a été réinitialisé avec succès."}


# --- /api/auth/verify-email/{uidb64}/{token}/ (flux secondaire, non utilise par frontend) ---

_EMAIL_VERIFY_PURPOSE = "email_verify"


@router.get("/api/auth/verify-email/{uidb64}/{token}/")
def verify_email(uidb64: str, token: str, db: Session = Depends(get_db)):
    user_id = verify_uid_token(uidb64, token, _EMAIL_VERIFY_PURPOSE)
    if user_id is None:
        return JSONResponse(
            status_code=400, content={"detail": "Le lien de vérification est invalide ou a expiré."}
        )

    user = db.get(Utilisateur, user_id)
    if user is None:
        return JSONResponse(
            status_code=400, content={"detail": "Le lien de vérification est invalide ou a expiré."}
        )

    user.is_email_verified = True
    user.is_active = True
    db.commit()
    return {"message": "Votre adresse email a été vérifiée avec succès. Vous pouvez maintenant vous connecter."}


# --- /api/auth/logout/ (code mort cote Django - jamais monte dans authentication/urls.py -----
# expose ici, cout nul, ne casse rien d'existant) ---------------------------------------------


@router.post("/api/auth/logout/")
def logout(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    if not payload.refresh:
        return JSONResponse(status_code=400, content={"detail": "refresh_token manquant."})

    try:
        decoded = decode_token(payload.refresh)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    revoke_refresh_token(db, decoded.get("jti", ""))
    return {"message": "Déconnexion réussie"}
