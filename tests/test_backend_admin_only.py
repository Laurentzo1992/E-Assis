"""Verifie que les routes d'ecriture de /api/backend/api/ (publications, marches, resultats, lots,
domaines) sont bien reservees aux comptes staff (require_staff) - regression pour le trou
d'autorisation trouve en examinant le futur site d'administration : ces routes n'etaient gardees
que par "utilisateur connecte", pas par le role, ce qui permettait a n'importe quelle entreprise
inscrite de supprimer un bulletin ou fabriquer un faux resultat via l'API."""

from sqlalchemy import select

from api.database import SessionLocal
from api.models.utilisateur import Utilisateur
from tests.conftest import register_and_activate
from tests.test_entreprise import PASSWORD, _login_headers


def _promouvoir_staff(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(Utilisateur).where(Utilisateur.email == email))
        user.is_staff = True
        db.commit()
    finally:
        db.close()


def test_utilisateur_normal_ne_peut_pas_creer_de_publication(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    response = client.post(
        "/api/backend/api/publications/",
        headers=headers,
        json={"titre": "Bulletin", "numero": "1", "date_publication": "2026-01-01", "source": "DGCMEF"},
    )
    assert response.status_code == 403


def test_utilisateur_staff_peut_creer_et_supprimer_une_publication(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    _promouvoir_staff(unique_email)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/backend/api/publications/",
        headers=headers,
        json={"titre": "Bulletin", "numero": "1", "date_publication": "2026-01-01", "source": "DGCMEF"},
    )
    assert created.status_code == 201

    deleted = client.delete(f"/api/backend/api/publications/{created.json()['id']}/", headers=headers)
    assert deleted.status_code == 204


def test_utilisateur_normal_ne_peut_pas_creer_de_marche(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    response = client.post("/api/backend/api/marches/", headers=headers, json={"objet": "Fourniture de test"})
    assert response.status_code == 403


def test_utilisateur_normal_ne_peut_pas_creer_de_resultat(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    response = client.post("/api/backend/api/resultats/", headers=headers, json={"marche_id": 1})
    assert response.status_code == 403


def test_utilisateur_normal_ne_peut_pas_creer_de_lot(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    response = client.post("/api/backend/api/lots/", headers=headers, json={"marche_id": 1})
    assert response.status_code == 403


def test_utilisateur_normal_ne_peut_pas_creer_de_domaine_backend(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    response = client.post("/api/backend/api/domaines/", headers=headers, json={"libelle": "Test"})
    assert response.status_code == 403
