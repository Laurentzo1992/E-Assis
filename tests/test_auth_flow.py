from tests.conftest import get_activation_token, register_and_activate

PASSWORD = "MotDePasseSolide123"


def test_register_puis_activation_puis_login(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)

    response = client.post("/api/auth/login/", json={"email": unique_email, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert "access" in body and "refresh" in body


def test_login_avant_activation_echoue(client, unique_email):
    client.post("/api/auth/register/", json={"email": unique_email, "password": PASSWORD})

    response = client.post("/api/auth/login/", json={"email": unique_email, "password": PASSWORD})
    assert response.status_code == 400
    assert "non_field_errors" in response.json()


def test_activation_token_invalide(client):
    response = client.get("/api/auth/activate/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 400
    assert response.json() == {"error": "Lien invalide."}


def test_activation_deja_active_renvoie_message_different(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    token = get_activation_token(unique_email)

    response = client.get(f"/api/auth/activate/{token}/")
    assert response.status_code == 200
    assert response.json() == {"message": "Compte activé."}


def test_register_email_deja_utilise(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)

    response = client.post("/api/auth/register/", json={"email": unique_email, "password": PASSWORD})
    assert response.status_code == 400
    assert "email" in response.json()


def test_refresh_rotation_et_blacklist(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    login = client.post("/api/auth/login/", json={"email": unique_email, "password": PASSWORD}).json()

    refreshed = client.post("/api/token/refresh/", json={"refresh": login["refresh"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["access"] != login["access"]

    # L'ancien refresh est blackliste des la rotation (BLACKLIST_AFTER_ROTATION) : le reutiliser
    # doit maintenant echouer.
    reused = client.post("/api/token/refresh/", json={"refresh": login["refresh"]})
    assert reused.status_code == 401


def test_logout_revoque_le_refresh_token(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    login = client.post("/api/auth/login/", json={"email": unique_email, "password": PASSWORD}).json()

    logout = client.post("/api/auth/logout/", json={"refresh": login["refresh"]})
    assert logout.status_code == 200

    reused = client.post("/api/token/refresh/", json={"refresh": login["refresh"]})
    assert reused.status_code == 401


def test_profile_requiert_authentification(client):
    response = client.get("/api/auth/profile/")
    assert response.status_code == 401


def test_profile_get_et_update(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    login = client.post("/api/auth/login/", json={"email": unique_email, "password": PASSWORD}).json()
    headers = {"Authorization": f"Bearer {login['access']}"}

    profile = client.get("/api/auth/profile/", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == unique_email

    updated = client.put("/api/auth/profile/", headers=headers, json={"telephone": "70000000"})
    assert updated.status_code == 200
    assert updated.json()["telephone"] == "70000000"
