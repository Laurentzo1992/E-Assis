from api.database import SessionLocal
from api.models.abonnement import Abonnement
from api.models.entreprise import Entreprise
from api.models.utilisateur import Utilisateur
from api.routers.entreprise import MAX_ENTREPRISES_PAR_ABONNEMENT
from api.scripts.extract_bulletin import _find_entreprise_attributaire
from llm_service.extraction_prompts import AvisExtrait
from tests.conftest import register_and_activate

PASSWORD = "MotDePasseSolide123"


def _avis_resultat(**kwargs) -> AvisExtrait:
    return AvisExtrait(type_avis="resultat", organisme="X", objet="Y", **kwargs)


def _login_headers(client, email: str) -> dict:
    login = client.post("/api/auth/login/", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {login['access']}"}


def test_creer_et_lister_ses_entreprises(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Ma Boite", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    assert created.status_code == 201
    entreprise_id = created.json()["id"]

    listed = client.get("/api/entreprise/entreprises/", headers=headers)
    assert listed.status_code == 200
    assert any(e["id"] == entreprise_id for e in listed.json())


def test_utilisateur_langue_colonne_a_un_defaut_fr_non_nullable():
    # Cf. api/alembic/versions/p6q7r8s9t0u1_langue_multilingue.py : server_default='fr', NOT NULL.
    colonne = Utilisateur.__table__.c.langue
    assert colonne.nullable is False
    assert colonne.server_default is not None


def test_entreprise_langue_alertes_colonne_nullable_sans_defaut_serveur():
    # Contrairement a Utilisateur.langue : nullable, pre-remplie applicativement (pas de
    # server_default) - cf. meme migration.
    colonne = Entreprise.__table__.c.langue_alertes
    assert colonne.nullable is True
    assert colonne.server_default is None


def test_profil_expose_et_accepte_la_langue(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    profil = client.get("/api/auth/profile/", headers=headers)
    assert profil.status_code == 200
    assert profil.json()["langue"] == "fr"

    maj = client.put("/api/auth/profile/", headers=headers, json={"langue": "en"})
    assert maj.status_code == 200
    assert maj.json()["langue"] == "en"

    relu = client.get("/api/auth/profile/", headers=headers)
    assert relu.json()["langue"] == "en"


def test_creer_entreprise_prerempli_langue_alertes_avec_celle_du_compte(client, unique_email):
    # Meme pattern que l'email de contact (cf. test_creer_entreprise_prerempli_email_avec_celui_du_compte_si_absent
    # ci-dessous) : Entreprise.langue_alertes herite la langue du compte a la creation, mais reste
    # modifiable ensuite - garantit que le contenu des alertes a une langue par defaut sensee des
    # le premier envoi, meme si le gerant n'y a jamais touche explicitement.
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    maj_profil = client.put("/api/auth/profile/", headers=headers, json={"langue": "en"})
    assert maj_profil.status_code == 200

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite EN", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    assert created.status_code == 201
    assert created.json()["langue_alertes"] == "en"


def test_creer_entreprise_respecte_la_langue_alertes_explicite_si_fournie(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={
            "nom": "Boite Langue Explicite",
            "numero_identification": f"ID2-{unique_email}",
            "rccm": ("2" + unique_email)[:20],
            "langue_alertes": "mos",
        },
    )
    assert created.status_code == 201
    assert created.json()["langue_alertes"] == "mos"

    maj = client.put(
        f"/api/entreprise/entreprises/{created.json()['id']}/",
        headers=headers,
        json={"langue_alertes": "en", "domaine_ids": [], "secteur_ids": []},
    )
    assert maj.status_code == 200
    assert maj.json()["langue_alertes"] == "en"


def test_creer_entreprise_prerempli_email_avec_celui_du_compte_si_absent(client, unique_email):
    # Les alertes email utilisent toujours Entreprise.email, sans repli sur l'email du compte
    # (cf. api/scripts/match_and_alert.py, _envoyer_alerte) - garantir ce champ non-vide des la
    # creation evite qu'une entreprise sans email de contact explicite ne recoive jamais rien.
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Sans Email Explicite", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    assert created.status_code == 201
    assert created.json()["email"] == unique_email


def test_creer_entreprise_respecte_lemail_explicite_si_fourni(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    email_contact = f"contact-{unique_email}"

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={
            "nom": "Boite Avec Email Explicite",
            "numero_identification": f"ID2-{unique_email}",
            "rccm": ("2" + unique_email)[:20],
            "email": email_contact,
        },
    )
    assert created.status_code == 201
    assert created.json()["email"] == email_contact

    # Modifiable ensuite (cf. update_entreprise, deja teste ailleurs pour les domaines/secteurs) -
    # confirme juste ici que le pre-remplissage a la creation ne verrouille pas le champ.
    nouvel_email = f"change-{unique_email}"
    maj = client.put(
        f"/api/entreprise/entreprises/{created.json()['id']}/",
        headers=headers,
        json={"email": nouvel_email, "domaine_ids": [], "secteur_ids": []},
    )
    assert maj.status_code == 200
    assert maj.json()["email"] == nouvel_email


def test_deuxieme_entreprise_partage_labonnement_de_la_premiere(client, unique_email):
    # Cas reel qui a motive ce correctif : un meme gerant (compte "vuneemtech@gmail.com") avec
    # deux entreprises ("LOGO SERVICES" et "VTECH") se retrouvait avec deux abonnements
    # independants, chacun avec son propre essai de 30 jours - l'abonnement doit couvrir le
    # compte, pas chaque entreprise separement.
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    premiere = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Premiere Boite", "numero_identification": f"ID1-{unique_email}", "rccm": ("1" + unique_email)[:20]},
    )
    assert premiere.status_code == 201
    premiere_id = premiere.json()["id"]

    seconde = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Seconde Boite", "numero_identification": f"ID2-{unique_email}", "rccm": ("2" + unique_email)[:20]},
    )
    assert seconde.status_code == 201
    seconde_id = seconde.json()["id"]

    db = SessionLocal()
    try:
        nb_abonnements = (
            db.query(Abonnement)
            .join(Utilisateur, Utilisateur.id == Abonnement.utilisateur_id)
            .filter(Utilisateur.email == unique_email)
            .count()
        )
        assert nb_abonnements == 1
    finally:
        db.close()

    abo_1 = client.get(f"/api/paiement/abonnement/{premiere_id}/", headers=headers).json()
    abo_2 = client.get(f"/api/paiement/abonnement/{seconde_id}/", headers=headers).json()
    assert abo_1["date_fin_essai"] == abo_2["date_fin_essai"]


def test_troisieme_entreprise_refusee_limite_atteinte(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    for i in range(MAX_ENTREPRISES_PAR_ABONNEMENT):
        reponse = client.post(
            "/api/entreprise/entreprises/",
            headers=headers,
            json={
                "nom": f"Boite {i}",
                "numero_identification": f"ID{i}-{unique_email}",
                "rccm": (f"{i}" + unique_email)[:20],
            },
        )
        assert reponse.status_code == 201, reponse.text

    en_trop = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={
            "nom": "Boite En Trop",
            "numero_identification": f"IDX-{unique_email}",
            "rccm": ("x" + unique_email)[:20],
        },
    )
    assert en_trop.status_code == 400


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
        json={"nom": "Boite A", "numero_identification": f"ID-A-{unique_email}", "rccm": "1" + unique_email.replace("@","").replace(".","")[:13]},
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
        json={"nom": "Boite Active", "numero_identification": f"ID-ACT-{unique_email}", "rccm": "2" + unique_email.replace("@","").replace(".","")[:13]},
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


def test_maj_domaines_active_le_rattrapage_mais_pas_un_simple_renommage(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)

    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Rattrapage", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    entreprise_id = created.json()["id"]

    domaine = client.post(
        "/api/entreprise/domaines/", headers=headers, json={"libelle": f"Informatique-{unique_email}"}
    )
    assert domaine.status_code == 201
    domaine_id = domaine.json()["id"]

    db = SessionLocal()
    assert db.get(Entreprise, entreprise_id).profil_a_rattraper is False
    db.close()

    # Changer uniquement le nom (domaine_ids/secteur_ids vides comme a la creation) : pas de
    # changement reel de profil, le flag ne doit pas bouger.
    renomme = client.put(
        f"/api/entreprise/entreprises/{entreprise_id}/",
        headers=headers,
        json={"nom": "Boite Rattrapage Renommee", "domaine_ids": [], "secteur_ids": []},
    )
    assert renomme.status_code == 200
    db = SessionLocal()
    assert db.get(Entreprise, entreprise_id).profil_a_rattraper is False
    db.close()

    # Ajouter un domaine : c'est un reel changement de profil, doit activer le flag.
    maj = client.put(
        f"/api/entreprise/entreprises/{entreprise_id}/",
        headers=headers,
        json={"domaine_ids": [domaine_id], "secteur_ids": []},
    )
    assert maj.status_code == 200
    db = SessionLocal()
    assert db.get(Entreprise, entreprise_id).profil_a_rattraper is True
    db.close()


def _creer_entreprise(client, headers, unique_email, **overrides):
    court = unique_email.replace("@", "").replace(".", "")[:15]
    payload = {
        "nom": "Entreprise Cascade",
        "numero_identification": f"IFU-{court}",
        "rccm": f"RCCM-{court}",
        "telephone": f"7{abs(hash(unique_email)) % 10_000_000:07d}",
    }
    payload.update(overrides)
    created = client.post("/api/entreprise/entreprises/", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def test_find_entreprise_attributaire_priorite_rccm_sur_nom(client, unique_email):
    """Un RCCM identique doit l'emporter meme si le nom extrait par le LLM ne correspond pas du
    tout - cf. discussion : le nom seul se prete a des correspondances approximatives, le RCCM est
    une preuve quasi certaine quand il est present dans le texte."""
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    entreprise = _creer_entreprise(client, headers, unique_email)

    db = SessionLocal()
    try:
        avis = _avis_resultat(
            entreprise_attributaire_nom="Un Nom Totalement Different",
            entreprise_attributaire_rccm=entreprise["rccm"],
        )
        trouvee = _find_entreprise_attributaire(db, avis)
        assert trouvee is not None
        assert trouvee.id == entreprise["id"]
    finally:
        db.close()


def test_find_entreprise_attributaire_repli_sur_nom_si_pas_de_rccm_ifu(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    entreprise = _creer_entreprise(client, headers, unique_email, nom=f"Boite Unique {unique_email}")

    db = SessionLocal()
    try:
        avis = _avis_resultat(entreprise_attributaire_nom=f"Boite Unique {unique_email}")
        trouvee = _find_entreprise_attributaire(db, avis)
        assert trouvee is not None
        assert trouvee.id == entreprise["id"]
    finally:
        db.close()


def test_find_entreprise_attributaire_aucune_correspondance(client, unique_email):
    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    _creer_entreprise(client, headers, unique_email)

    db = SessionLocal()
    try:
        avis = _avis_resultat(entreprise_attributaire_nom="Une Entreprise Qui N'existe Pas Du Tout")
        assert _find_entreprise_attributaire(db, avis) is None
    finally:
        db.close()
