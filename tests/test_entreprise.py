from tests.conftest import register_and_activate

PASSWORD = "MotDePasseSolide123"


def _login_headers(client, email: str) -> dict:
    login = client.post("/api/auth/login/", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {login['access']}"}


def test_creer_et_lister_ses_entreprises(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Ma Boite", "numero_identification": f"ID-{unique_email}", "siret": unique_email[:20]},
    )
    assert created.status_code == 201
    entreprise_id = created.json()["id"]

    listed = client.get("/api/entreprise/entreprises/", headers=headers)
    assert listed.status_code == 200
    assert any(e["id"] == entreprise_id for e in listed.json())


def test_isolation_par_proprietaire(client, unique_email):
    email_a = f"a-{unique_email}"
    email_b = f"b-{unique_email}"
    register_and_activate(client, email_a, PASSWORD)
    register_and_activate(client, email_b, PASSWORD)
    headers_a = _login_headers(client, email_a)
    headers_b = _login_headers(client, email_b)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers_a,
        json={"nom": "Boite A", "numero_identification": f"ID-A-{unique_email}", "siret": "1" + unique_email.replace("@","").replace(".","")[:13]},
    )
    entreprise_id = created.json()["id"]

    # L'utilisateur B ne doit ni la voir dans sa liste, ni pouvoir y acceder directement.
    listed_b = client.get("/api/entreprise/entreprises/", headers=headers_b)
    assert all(e["id"] != entreprise_id for e in listed_b.json())

    direct_access_b = client.get(f"/api/entreprise/entreprises/{entreprise_id}/", headers=headers_b)
    assert direct_access_b.status_code == 404


def test_active_et_set_active(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    no_active_yet = client.get("/api/entreprise/entreprises/active/", headers=headers)
    assert no_active_yet.status_code == 404

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Active", "numero_identification": f"ID-ACT-{unique_email}", "siret": "2" + unique_email.replace("@","").replace(".","")[:13]},
    )
    entreprise_id = created.json()["id"]

    set_active = client.post("/api/entreprise/entreprises/set-active/", headers=headers, json={"entreprise_id": entreprise_id})
    assert set_active.status_code == 200

    active = client.get("/api/entreprise/entreprises/active/", headers=headers)
    assert active.status_code == 200
    assert active.json()["id"] == entreprise_id


def test_entreprise_requiert_authentification(client):
    response = client.get("/api/entreprise/entreprises/")
    assert response.status_code in (401, 403)
