"""Tests d'integration : tournent contre la vraie base Postgres de docker-compose
(DATABASE_URL par defaut = celle exposee sur localhost:5432) - pas de mock de la DB, seul
l'envoi d'email reel est court-circuite (pas de dependance a un compte SMTP dans les tests).
"""

import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://eassis:eassis_dev_password_123@localhost:5432/eassis")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.database import SessionLocal
from api.main import app
from api.models.utilisateur import Utilisateur


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    monkeypatch.setattr("api.routers.auth.send_activation_email", lambda *a, **k: None)
    monkeypatch.setattr("api.routers.auth.send_password_reset_email", lambda *a, **k: None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def unique_email():
    return f"pytest-{uuid.uuid4().hex[:12]}@example.com"


def get_activation_token(email: str) -> str:
    db = SessionLocal()
    try:
        user = db.scalar(select(Utilisateur).where(Utilisateur.email == email))
        return str(user.activation_token)
    finally:
        db.close()


def register_and_activate(client: TestClient, email: str, password: str) -> None:
    response = client.post("/api/auth/register/", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    token = get_activation_token(email)
    response = client.get(f"/api/auth/activate/{token}/")
    assert response.status_code == 200, response.text
