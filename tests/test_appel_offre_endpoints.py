"""Regression : GET /api/backend/api/appels-offres/ (liste et detail) renvoyait 500 des que la
table appels_offre contenait une ligne. AppelOffreResponse etend MarcheResponse (parite avec
l'heritage multi-table Django d'origine) mais l'endpoint renvoyait l'objet AppelOffre brut, qui ne
porte pas directement les champs de Marche (id/publication/objet/...) - jamais declenche avant
que _upsert_avis() (api/scripts/extract_bulletin.py) ne cree enfin de vraies lignes AppelOffre."""

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


def _creer_publication_staff(client, headers):
    created = client.post(
        "/api/backend/api/publications/",
        headers=headers,
        json={"titre": "Bulletin", "numero": "1", "date_publication": "2026-01-01", "source": "DGCMEF"},
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_creer_lister_et_lire_un_appel_offre(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    _promouvoir_staff(unique_email)
    headers = _login_headers(client, unique_email)
    publication_id = _creer_publication_staff(client, headers)

    created = client.post(
        "/api/backend/api/appels-offres/",
        headers=headers,
        json={
            "publication_id": publication_id,
            "objet": "Fourniture de test appel_offre",
            "referenceDossier": "AO-TEST-001",
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["objet"] == "Fourniture de test appel_offre"
    assert data["referenceDossier"] == "AO-TEST-001"
    marche_id = data["id"]

    listed = client.get("/api/backend/api/appels-offres/", headers=headers)
    assert listed.status_code == 200
    assert any(ao["id"] == marche_id for ao in listed.json())

    detail = client.get(f"/api/backend/api/appels-offres/{marche_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == marche_id
    assert detail.json()["objet"] == "Fourniture de test appel_offre"
