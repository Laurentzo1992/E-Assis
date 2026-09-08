"""Tests d'integration : tournent contre la vraie base Postgres de docker-compose
(DATABASE_URL par defaut = celle exposee sur localhost:5432) - pas de mock de la DB, seul
l'envoi d'email reel est court-circuite (pas de dependance a un compte SMTP dans les tests).

Isolation : chaque test tourne dans sa PROPRE transaction Postgres, jamais commit (rollback
systematique en fin de test, cf. `_transaction_isolee_par_test` ci-dessous) - aucune donnee de
test n'atteint jamais la base de facon persistante, meme si le test plante en cours de route ou
si la suite est interrompue. Remplace un premier essai (purge apres-coup en debut/fin de session,
cf. historique git) qui laissait quand meme les donnees visibles en base PENDANT toute
l'execution de la suite, et ne protegeait pas contre une interruption en plein milieu.
"""

import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://eassis:eassis_dev_password_123@localhost:5432/eassis")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.database import SessionLocal, engine
from api.main import app
from api.models.utilisateur import Utilisateur


@pytest.fixture(autouse=True)
def _transaction_isolee_par_test():
    """Ouvre une connexion + une transaction Postgres, reconfigure `SessionLocal` (le MEME objet
    sessionmaker que tout le reste du code importe et appelle - routers, scripts, tests) pour s'y
    lier, puis annule tout a la fin du test (rollback), quoi qu'il se soit passe.

    `SessionLocal.configure(bind=...)` modifie l'objet sessionmaker EN PLACE plutot que de le
    remplacer : tout code qui a deja fait `from api.database import SessionLocal` (donc toute
    l'appli, chargee une fois au demarrage de la suite via `from api.main import app` plus bas)
    continue d'appeler le meme objet, qui cree desormais des sessions liees a la connexion de
    test - aucun `dependency_overrides` FastAPI necessaire, `get_db()` (inchangee) en beneficie
    automatiquement.

    `join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0) est ce qui rend ca transparent
    pour le code applicatif : un `db.commit()` a l'interieur d'un routeur ou d'un script ne cloture
    plus la transaction EXTERIEURE (celle geree ici) mais une simple SAVEPOINT, immediatement
    remplacee par une nouvelle - le code testé continue de fonctionner sans modification, tout en
    restant entierement annulable a la fin du test."""
    connexion = engine.connect()
    transaction = connexion.begin()
    SessionLocal.configure(bind=connexion, join_transaction_mode="create_savepoint")
    try:
        yield
    finally:
        SessionLocal.configure(bind=engine)
        transaction.rollback()
        connexion.close()


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
