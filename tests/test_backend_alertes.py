from datetime import datetime, timezone

from api.database import SessionLocal
from api.models.backend import Publication
from tests.conftest import register_and_activate
from tests.test_entreprise import PASSWORD, _login_headers


def _creer_entreprise(client, headers, unique_email, suffix):
    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={
            "nom": f"Boite {suffix}",
            "numero_identification": f"ID-{suffix}-{unique_email}",
            "rccm": (suffix + unique_email)[:20],
        },
    )
    assert created.status_code == 201
    return created.json()["id"]


def _creer_publication():
    # Cree directement en base plutot que via /api/backend/api/publications/ : cet endpoint est
    # reserve aux admins (require_staff), et cette fixture n'a besoin que d'une Publication
    # existante pour tester le scoping des alertes, pas de tester la creation elle-meme.
    db = SessionLocal()
    try:
        publication = Publication(
            titre="Bulletin",
            numero=f"pytest-{datetime.now(timezone.utc).timestamp()}",
            date_publication=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source="DGCMEF",
        )
        db.add(publication)
        db.commit()
        db.refresh(publication)
        return publication.id
    finally:
        db.close()


def _creer_alerte(client, headers, entreprise_id, publication_id, contenu="Un marche vous correspond"):
    created = client.post(
        "/api/backend/api/alertes/",
        headers=headers,
        json={
            "entreprise_id": entreprise_id,
            "publication_id": publication_id,
            "type_alerte": "marche",
            "date_alerte": "2026-01-01T00:00:00Z",
            "contenu_alerte": contenu,
            "canal_alerte": "email",
        },
    )
    assert created.status_code == 201
    return created.json()


def test_isolation_alertes_par_proprietaire(client, unique_email):
    email_a = f"a-{unique_email}"
    email_b = f"b-{unique_email}"
    register_and_activate(client, email_a, PASSWORD)
    register_and_activate(client, email_b, PASSWORD)
    headers_a = _login_headers(client, email_a)
    headers_b = _login_headers(client, email_b)

    entreprise_a = _creer_entreprise(client, headers_a, unique_email, "A")
    publication_id = _creer_publication()

    created = client.post(
        "/api/backend/api/alertes/",
        headers=headers_a,
        json={
            "entreprise_id": entreprise_a,
            "publication_id": publication_id,
            "type_alerte": "marche",
            "date_alerte": "2026-01-01T00:00:00Z",
            "contenu_alerte": "Un marche vous correspond",
            "canal_alerte": "email",
        },
    )
    assert created.status_code == 201
    alerte_id = created.json()["id"]

    # B ne doit jamais voir l'alerte de A, ni dans la liste ni par acces direct.
    listed_b = client.get("/api/backend/api/alertes/", headers=headers_b)
    assert listed_b.status_code == 200
    assert all(a["id"] != alerte_id for a in listed_b.json())

    direct_b = client.get(f"/api/backend/api/alertes/{alerte_id}/", headers=headers_b)
    assert direct_b.status_code == 404

    delete_b = client.delete(f"/api/backend/api/alertes/{alerte_id}/", headers=headers_b)
    assert delete_b.status_code == 404

    # A voit bien sa propre alerte.
    listed_a = client.get("/api/backend/api/alertes/", headers=headers_a)
    assert any(a["id"] == alerte_id for a in listed_a.json())


def test_creation_alerte_refuse_entreprise_dautrui(client, unique_email):
    email_a = f"a-{unique_email}"
    email_b = f"b-{unique_email}"
    register_and_activate(client, email_a, PASSWORD)
    register_and_activate(client, email_b, PASSWORD)
    headers_a = _login_headers(client, email_a)
    headers_b = _login_headers(client, email_b)

    entreprise_a = _creer_entreprise(client, headers_a, unique_email, "A2")
    publication_id = _creer_publication()

    # B tente de creer une alerte pour l'entreprise de A - doit echouer.
    response = client.post(
        "/api/backend/api/alertes/",
        headers=headers_b,
        json={
            "entreprise_id": entreprise_a,
            "publication_id": publication_id,
            "type_alerte": "marche",
            "date_alerte": "2026-01-01T00:00:00Z",
            "contenu_alerte": "Tentative non autorisee",
            "canal_alerte": "email",
        },
    )
    assert response.status_code == 404


def test_alerte_nait_non_lue(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    entreprise_id = _creer_entreprise(client, headers, unique_email, "L1")
    publication_id = _creer_publication()

    alerte = _creer_alerte(client, headers, entreprise_id, publication_id)
    assert alerte["lu"] is False


def test_marquer_alertes_lues(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    entreprise_id = _creer_entreprise(client, headers, unique_email, "L2")
    publication_id = _creer_publication()

    alerte_1 = _creer_alerte(client, headers, entreprise_id, publication_id, "Marche 1")
    alerte_2 = _creer_alerte(client, headers, entreprise_id, publication_id, "Marche 2")

    response = client.post("/api/backend/api/alertes/marquer-lues/", headers=headers)
    assert response.status_code == 204

    listed = {a["id"]: a["lu"] for a in client.get("/api/backend/api/alertes/", headers=headers).json()}
    assert listed[alerte_1["id"]] is True
    assert listed[alerte_2["id"]] is True


def test_marquer_alertes_lues_isolation(client, unique_email):
    email_a = f"a-{unique_email}"
    email_b = f"b-{unique_email}"
    register_and_activate(client, email_a, PASSWORD)
    register_and_activate(client, email_b, PASSWORD)
    headers_a = _login_headers(client, email_a)
    headers_b = _login_headers(client, email_b)

    entreprise_a = _creer_entreprise(client, headers_a, unique_email, "L3")
    publication_id = _creer_publication()
    alerte_a = _creer_alerte(client, headers_a, entreprise_a, publication_id)

    # B marque SES alertes comme lues (aucune) - ne doit pas toucher celle de A.
    response = client.post("/api/backend/api/alertes/marquer-lues/", headers=headers_b)
    assert response.status_code == 204

    listed_a = {a["id"]: a["lu"] for a in client.get("/api/backend/api/alertes/", headers=headers_a).json()}
    assert listed_a[alerte_a["id"]] is False
