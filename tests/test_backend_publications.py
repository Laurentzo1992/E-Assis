from datetime import datetime, timezone

from api.database import SessionLocal
from api.models.backend import Publication
from tests.conftest import register_and_activate
from tests.test_entreprise import PASSWORD, _login_headers


def test_pdf_url_presigne_pour_une_publication(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    # Cree directement en base : /api/backend/api/publications/ est reserve aux admins
    # (require_staff), et ce test verifie l'URL presignee, pas la creation elle-meme.
    db = SessionLocal()
    try:
        publication = Publication(
            titre="Bulletin quotidien n°9999",
            numero="9999",
            date_publication=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source="DGCMEF",
        )
        db.add(publication)
        db.commit()
        db.refresh(publication)
        publication_id = publication.id
    finally:
        db.close()

    response = client.get(f"/api/backend/api/publications/{publication_id}/pdf-url/", headers=headers)
    assert response.status_code == 200
    url = response.json()["url"]
    assert url.startswith("http://localhost:9000/")
    assert "pdf/quotidien/9999.pdf" in url


def test_pdf_url_publication_inexistante(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    response = client.get("/api/backend/api/publications/999999999/pdf-url/", headers=headers)
    assert response.status_code == 404
