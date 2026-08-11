"""Tests de l'abonnement annuel (essai gratuit + paiement CinetPay) : appels HTTP CinetPay mockes,
aucune dependance a un vrai compte ni a un hebergement public (le webhook n'est jamais appele
reellement par CinetPay dans ces tests, seulement simule via le TestClient)."""

from datetime import datetime, timedelta, timezone

import pytest

from api.payment_client import PaiementError, initier_paiement, verifier_transaction
from api.routers.paiement import _jours_restants, _statut_courant
from tests.conftest import register_and_activate
from tests.test_entreprise import PASSWORD, _login_headers

# --- payment_client (appels HTTP mockes) -------------------------------------------------------


def test_initier_paiement_succes(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"code": "201", "data": {"payment_url": "https://checkout.cinetpay.com/xyz"}}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("api.payment_client.requests.post", fake_post)

    url = initier_paiement(
        reference="ref-1", montant="50000", devise="XOF", description="Abonnement",
        notify_url="https://x/hook", return_url="https://x/retour",
    )

    assert url == "https://checkout.cinetpay.com/xyz"
    assert captured["json"]["transaction_id"] == "ref-1"
    assert captured["json"]["currency"] == "XOF"
    assert captured["url"].endswith("/payment")


def test_initier_paiement_erreur_api(monkeypatch):
    class FakeResponse:
        status_code = 400
        def json(self):
            return {"code": "600", "message": "cle invalide"}

    monkeypatch.setattr("api.payment_client.requests.post", lambda *a, **k: FakeResponse())

    with pytest.raises(PaiementError):
        initier_paiement(
            reference="ref-1", montant="50000", devise="XOF", description="x",
            notify_url="https://x", return_url="https://x",
        )


def test_initier_paiement_erreur_reseau(monkeypatch):
    import requests

    def fake_post(*a, **k):
        raise requests.exceptions.ConnectionError("DNS injoignable")

    monkeypatch.setattr("api.payment_client.requests.post", fake_post)

    with pytest.raises(PaiementError):
        initier_paiement(
            reference="ref-1", montant="50000", devise="XOF", description="x",
            notify_url="https://x", return_url="https://x",
        )


def test_verifier_transaction_erreur_reseau(monkeypatch):
    import requests

    def fake_post(*a, **k):
        raise requests.exceptions.Timeout("delai depasse")

    monkeypatch.setattr("api.payment_client.requests.post", fake_post)

    with pytest.raises(PaiementError):
        verifier_transaction("ref-1")


def test_verifier_transaction_acceptee(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"code": "00", "data": {"status": "ACCEPTED"}}

    monkeypatch.setattr("api.payment_client.requests.post", lambda *a, **k: FakeResponse())

    assert verifier_transaction("ref-1") is True


def test_verifier_transaction_refusee(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"code": "00", "data": {"status": "REFUSED"}}

    monkeypatch.setattr("api.payment_client.requests.post", lambda *a, **k: FakeResponse())

    assert verifier_transaction("ref-1") is False


# --- _statut_courant / _jours_restants (logique pure) -------------------------------------------


def _abonnement(**kwargs):
    class FakeAbonnement:
        pass

    a = FakeAbonnement()
    a.statut = kwargs.get("statut", "essai")
    a.date_debut_essai = kwargs.get("date_debut_essai")
    a.date_fin_essai = kwargs["date_fin_essai"]
    a.date_fin_abonnement = kwargs.get("date_fin_abonnement")
    return a


def test_statut_essai_en_cours():
    maintenant = datetime.now(timezone.utc)
    abonnement = _abonnement(date_fin_essai=maintenant + timedelta(days=5))
    assert _statut_courant(abonnement, maintenant) == "essai"


def test_statut_essai_expire_sans_paiement():
    maintenant = datetime.now(timezone.utc)
    abonnement = _abonnement(date_fin_essai=maintenant - timedelta(days=1))
    assert _statut_courant(abonnement, maintenant) == "expire"


def test_statut_actif_avec_abonnement_paye_en_cours():
    maintenant = datetime.now(timezone.utc)
    abonnement = _abonnement(
        statut="actif", date_fin_essai=maintenant - timedelta(days=100), date_fin_abonnement=maintenant + timedelta(days=300)
    )
    assert _statut_courant(abonnement, maintenant) == "actif"


def test_statut_expire_si_abonnement_paye_depasse():
    maintenant = datetime.now(timezone.utc)
    abonnement = _abonnement(
        statut="actif", date_fin_essai=maintenant - timedelta(days=400), date_fin_abonnement=maintenant - timedelta(days=1)
    )
    assert _statut_courant(abonnement, maintenant) == "expire"


def test_jours_restants_essai():
    maintenant = datetime.now(timezone.utc)
    abonnement = _abonnement(date_fin_essai=maintenant + timedelta(days=5, hours=1))
    assert _jours_restants(abonnement, "essai", maintenant) == 5


def test_jours_restants_expire_toujours_zero():
    maintenant = datetime.now(timezone.utc)
    abonnement = _abonnement(date_fin_essai=maintenant - timedelta(days=1))
    assert _jours_restants(abonnement, "expire", maintenant) == 0


# --- Tarif (lu en base, endpoint public) ---------------------------------------------------------


def test_tarif_public_sans_authentification(client):
    response = client.get("/api/paiement/tarif/")
    assert response.status_code == 200
    data = response.json()
    assert data["essai_gratuit_jours"] > 0
    assert float(data["prix_annuel"]) > 0
    assert data["devise"]


# --- Integration : creation d'entreprise -> essai automatique -----------------------------------


def test_creation_entreprise_demarre_un_essai_gratuit(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Essai", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    entreprise_id = created.json()["id"]

    response = client.get(f"/api/paiement/abonnement/{entreprise_id}/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["statut"] == "essai"
    assert data["jours_restants"] == 30 or data["jours_restants"] == 29  # arrondi selon l'heure exacte


def test_abonnement_isolation_par_proprietaire(client, unique_email):
    email_a = f"a-{unique_email}"
    email_b = f"b-{unique_email}"
    register_and_activate(client, email_a, PASSWORD)
    register_and_activate(client, email_b, PASSWORD)
    headers_a = _login_headers(client, email_a)
    headers_b = _login_headers(client, email_b)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers_a,
        json={"nom": "Boite A", "numero_identification": f"ID-A-{unique_email}", "rccm": ("A" + unique_email)[:20]},
    )
    entreprise_id = created.json()["id"]

    response = client.get(f"/api/paiement/abonnement/{entreprise_id}/", headers=headers_b)
    assert response.status_code == 404

    response = client.post("/api/paiement/initier/", headers=headers_b, json={"entreprise_id": entreprise_id})
    assert response.status_code == 404


# --- Integration : initiation + webhook ----------------------------------------------------------


def test_initier_paiement_endpoint(client, unique_email, monkeypatch):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Paie", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    entreprise_id = created.json()["id"]

    monkeypatch.setattr("api.routers.paiement.initier_paiement", lambda **kwargs: "https://checkout.cinetpay.com/abc")

    response = client.post("/api/paiement/initier/", headers=headers, json={"entreprise_id": entreprise_id})

    assert response.status_code == 200
    assert response.json()["url"] == "https://checkout.cinetpay.com/abc"


def test_webhook_prolonge_abonnement_et_reste_idempotent(client, unique_email, monkeypatch):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Webhook", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    entreprise_id = created.json()["id"]

    monkeypatch.setattr("api.routers.paiement.initier_paiement", lambda **kwargs: "https://checkout.cinetpay.com/abc")
    init_response = client.post("/api/paiement/initier/", headers=headers, json={"entreprise_id": entreprise_id})
    assert init_response.status_code == 200

    # Recupere la reference generee via la base plutot que de la reconstruire nous-memes.
    from api.database import SessionLocal
    from api.models.abonnement import Paiement

    db = SessionLocal()
    paiement = db.query(Paiement).order_by(Paiement.id.desc()).first()
    reference = paiement.reference
    db.close()

    monkeypatch.setattr("api.routers.paiement.verifier_transaction", lambda ref: True)

    webhook_response = client.post("/api/paiement/webhook/", data={"cpm_trans_id": reference})
    assert webhook_response.status_code == 204

    statut_response = client.get(f"/api/paiement/abonnement/{entreprise_id}/", headers=headers)
    assert statut_response.json()["statut"] == "actif"

    # Rejeu du webhook (CinetPay peut renvoyer plusieurs fois la meme notification) : ne doit pas
    # prolonger une seconde fois.
    date_fin_apres_premier = statut_response.json()["date_fin_abonnement"]
    webhook_response_2 = client.post("/api/paiement/webhook/", data={"cpm_trans_id": reference})
    assert webhook_response_2.status_code == 204
    statut_response_2 = client.get(f"/api/paiement/abonnement/{entreprise_id}/", headers=headers)
    assert statut_response_2.json()["date_fin_abonnement"] == date_fin_apres_premier
