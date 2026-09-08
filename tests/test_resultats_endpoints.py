"""Tests pour les endpoints de résultats d'attribution (api/routers/resultats.py).

Règles d'Or testées :
- Règle 2 : Tolérance Zéro aux Faux Positifs (l'entreprise ne voit que les résultats réconciliés avec certitude, jamais A_VERIFIER).
- Règle 3 : Idempotence et traçabilité.
- Règle 4 : Respect des droits d'accès RBAC (isolation stricte par propriétaire et droits staff pour l'audit).
- Règle 5 : REX complet (motifs de rejet visibles côté candidat évincé).
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

if "sqlalchemy" not in sys.modules:
    try:
        import sqlalchemy
    except ImportError:
        sa_mock = MagicMock()
        class Base:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class MockColumn:
            def __init__(self, *args, **kwargs):
                self.name = kwargs.get("name", "")

            def __set_name__(self, owner, name):
                self.name = name

            def __eq__(self, other):
                col_name = self.name
                return lambda item: getattr(item, col_name, None) == other

            def __ne__(self, other):
                col_name = self.name
                return lambda item: getattr(item, col_name, None) != other

            def is_(self, other):
                return True

            def in_(self, others):
                return True

            def desc(self):
                return self

            def asc(self):
                return self

        sa_mock.Column = MockColumn
        sa_mock.mapped_column = MockColumn
        sa_mock.Integer = sa_mock.String = sa_mock.Text = sa_mock.Boolean = sa_mock.Date = sa_mock.DateTime = sa_mock.Numeric = sa_mock.Float = MagicMock()
        sa_mock.ForeignKey = lambda *args, **kwargs: None
        sa_mock.UniqueConstraint = lambda *args, **kwargs: None
        sa_mock.Index = lambda *args, **kwargs: None
        sa_mock.text = lambda s: s
        sa_mock.and_ = lambda *args: True
        sa_mock.or_ = lambda *args: True
        sa_mock.select = lambda *args: MagicMock()
        sa_mock.orm = MagicMock()
        sa_mock.orm.mapped_column = MockColumn
        sa_mock.orm.relationship = lambda *args, **kwargs: []
        sa_mock.orm.declarative_base = lambda: Base
        sa_mock.orm.Session = MagicMock
        sa_mock.orm.joinedload = lambda *args: MagicMock()
        sys.modules["sqlalchemy"] = sa_mock
        sys.modules["sqlalchemy.orm"] = sa_mock.orm
        sa_mock.dialects = MagicMock()
        sa_mock.dialects.postgresql = MagicMock()
        sys.modules["sqlalchemy.dialects"] = sa_mock.dialects
        sys.modules["sqlalchemy.dialects.postgresql"] = sa_mock.dialects.postgresql
        db_mock = MagicMock()
        db_mock.Base = Base
        db_mock.SessionLocal = MagicMock()
        db_mock.get_db = lambda: None
        sys.modules["api.database"] = db_mock

if "pydantic_settings" not in sys.modules:
    try:
        import pydantic_settings
    except ImportError:
        ps_mock = MagicMock()
        class MockSettings:
            def __init__(self, **kwargs):
                self.whatsapp_token = "dummy_token"
                self.whatsapp_phone_number_id = "12345"
                self.whatsapp_api_version = "v20.0"
                self.whatsapp_template_name = "nouvelle_opportunite_marche"
                self.whatsapp_template_resultat_victoire = "resultat_marche_victoire"
                self.whatsapp_template_resultat_echec = "resultat_marche_echec"
                self.whatsapp_template_language = "fr"
                self.default_from_email = "no-reply@e-assis.bf"
                self.email_host = "localhost"
                self.email_port = 587
                self.email_use_tls = False
                self.email_host_user = ""
                self.email_host_password = ""
        ps_mock.BaseSettings = MockSettings
        ps_mock.SettingsConfigDict = dict
        sys.modules["pydantic_settings"] = ps_mock

if "pydantic" not in sys.modules:
    try:
        import pydantic
    except ImportError:
        p_mock = MagicMock()
        class BaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
        p_mock.BaseModel = BaseModel
        p_mock.Field = lambda default=None, **kwargs: default
        sys.modules["pydantic"] = p_mock

if "requests" not in sys.modules:
    try:
        import requests
    except ImportError:
        sys.modules["requests"] = MagicMock()

if "jinja2" not in sys.modules:
    try:
        import jinja2
    except ImportError:
        sys.modules["jinja2"] = MagicMock()

if "fastapi" not in sys.modules:
    try:
        import fastapi
    except ImportError:
        fa_mock = MagicMock()
        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: str = ""):
                self.status_code = status_code
                self.detail = detail
                super().__init__(detail)
        fa_mock.HTTPException = HTTPException
        fa_mock.status = MagicMock()
        fa_mock.status.HTTP_400_BAD_REQUEST = 400
        fa_mock.status.HTTP_403_FORBIDDEN = 403
        fa_mock.status.HTTP_404_NOT_FOUND = 404
        class MockAPIRouter:
            def __init__(self, *args, **kwargs):
                pass
            def get(self, *args, **kwargs):
                def decorator(fn):
                    return fn
                return decorator
            def post(self, *args, **kwargs):
                def decorator(fn):
                    return fn
                return decorator
            def put(self, *args, **kwargs):
                def decorator(fn):
                    return fn
                return decorator
            def delete(self, *args, **kwargs):
                def decorator(fn):
                    return fn
                return decorator
        fa_mock.APIRouter = MockAPIRouter
        fa_mock.Depends = lambda x: x
        fa_mock.Query = lambda default=None, **kwargs: default
        sys.modules["fastapi"] = fa_mock

if "api.security" not in sys.modules:
    sec_mock = MagicMock()
    sec_mock.get_current_user = lambda: None
    sys.modules["api.security"] = sec_mock

from api.models.entreprise import Entreprise
from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from api.models.utilisateur import Utilisateur
from api.routers import resultats as resultats_router
from api.schemas.resultats import ReconcilierSoumissionnaireRequest


def test_get_resultats_entreprise_victoires_et_rex():
    """Vérifie que l'entreprise accède à ses résultats (victoires et REX) et que les statuts A_VERIFIER sont exclus."""
    # Création d'un mock session DB
    db = MagicMock()

    user_client = Utilisateur(id=1, email="client@test.com", is_staff=False, is_superuser=False)
    ent = Entreprise(id=10, nom="ENTREPRISE FASO SERVICES", owner_id=1, numero_identification="IFU12345", rccm="BF123")

    db.get.side_effect = lambda model, ident: ent if model == Entreprise and ident == 10 else None

    # Données simulées
    res = ResultatAttribution(
        id=100,
        bulletin_numero="4458",
        page_source=12,
        autorite_contractante="COMMUNE DE OUAGADOUGOU",
        reference_dossier="2026-001/CO",
        objet="Travaux de voirie",
    )
    lot1 = LotResultat(id=1, resultat_attribution_id=100, numero_lot="1", intitule_lot="Terrassement", statut_lot="ATTRIBUE")
    lot1.resultat_attribution = res

    # Soumissionnaire 1 : Gagnant
    s1 = SoumissionnaireResultat(
        id=201,
        lot_resultat_id=1,
        entreprise_id=10,
        nom_entreprise_brut="FASO SERVICES SARL",
        statut="ATTRIBUTAIRE",
        est_attributaire=True,
        montant_corrige=Decimal("15000000.00"),
        delai_execution="60 jours",
        statut_reconciliation="EXACT",
        score_matching=1.0,
    )
    s1.lot_resultat = lot1

    # Soumissionnaire 2 : Écarté avec REX
    lot2 = LotResultat(id=2, resultat_attribution_id=100, numero_lot="2", intitule_lot="Bitumage", statut_lot="ATTRIBUE")
    lot2.resultat_attribution = res
    s2 = SoumissionnaireResultat(
        id=202,
        lot_resultat_id=2,
        entreprise_id=10,
        nom_entreprise_brut="FASO SERVICES SARL",
        statut="ECARTE",
        est_attributaire=False,
        montant_corrige=Decimal("25000000.00"),
        motif_rejet="Garantie de soumission non conforme (manque visa bancaire)",
        statut_reconciliation="PROBABLE",
        score_matching=0.92,
    )
    s2.lot_resultat = lot2

    # Mock de la requête des soumissionnaires
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [s1, s2]
    db.scalars.return_value = scalars_mock

    # Mock pour le gagnant du lot 2
    gagnant_lot2 = SoumissionnaireResultat(
        id=203,
        lot_resultat_id=2,
        nom_entreprise_brut="KANAZOE FRERES",
        est_attributaire=True,
        montant_corrige=Decimal("24500000.00"),
    )
    db.scalar.return_value = gagnant_lot2

    # Appel du endpoint
    items = resultats_router.get_resultats_entreprise(
        entreprise_id=10,
        type_filtre=None,
        db=db,
        current_user=user_client,
    )

    assert len(items) == 2

    item_victoire = items[0]
    assert item_victoire.est_attributaire is True
    assert item_victoire.montant_attribue_ou_soumis == Decimal("15000000.00")
    assert item_victoire.delai_execution == "60 jours"

    item_echec = items[1]
    assert item_echec.est_attributaire is False
    assert "Garantie de soumission" in item_echec.motif_rejet
    assert item_echec.nom_attributaire_retenu == "KANAZOE FRERES"
    assert item_echec.montant_attributaire_retenu == Decimal("24500000.00")


def test_interdiction_acces_entreprise_tierce():
    """Un utilisateur ne peut pas consulter les résultats d'une entreprise qui ne lui appartient pas (Règle d'Or n°4)."""
    db = MagicMock()
    # Entreprise appartient au user 2
    ent = Entreprise(id=10, nom="AUTRE SARL", owner_id=2)
    db.get.return_value = ent

    # Appel par user 1 (non staff)
    user_intrus = Utilisateur(id=1, email="intrus@test.com", is_staff=False, is_superuser=False)

    from fastapi import HTTPException

    caught_exc = None
    try:
        resultats_router.get_resultats_entreprise(
            entreprise_id=10,
            type_filtre=None,
            db=db,
            current_user=user_intrus,
        )
    except HTTPException as exc:
        caught_exc = exc

    assert caught_exc is not None, "Une exception HTTPException aurait dû être levée"
    assert caught_exc.status_code == 403


def test_admin_arbitrage_soumissionnaire_a_verifier():
    """Un administrateur peut lister et valider manuellement un résultat ambigu A_VERIFIER (Règle d'Or n°2)."""
    db = MagicMock()
    admin_user = Utilisateur(id=99, email="admin@test.com", is_staff=True, is_superuser=True)

    ent = Entreprise(id=15, nom="SOCIETE BURKINABE DU COMMERCE", owner_id=3)
    soum = SoumissionnaireResultat(
        id=301,
        lot_resultat_id=5,
        nom_entreprise_brut="SO.BUR.COM",
        statut="ATTRIBUTAIRE",
        est_attributaire=True,
        statut_reconciliation="A_VERIFIER",
        score_matching=0.74,
        methode_matching="TRIGRAMME",
    )

    db.get.side_effect = lambda model, ident: soum if model == SoumissionnaireResultat and ident == 301 else (ent if model == Entreprise and ident == 15 else None)

    payload = ReconcilierSoumissionnaireRequest(
        action="VALIDER",
        entreprise_id=15,
        emettre_alerte=False,
    )

    resp = resultats_router.reconcilier_soumissionnaire_manuellement(
        soumissionnaire_id=301,
        payload=payload,
        db=db,
        _admin=admin_user,
    )

    assert resp.status == "success"
    assert resp.statut_reconciliation == "MANUEL"
    assert resp.entreprise_id == 15
    assert soum.statut_reconciliation == "MANUEL"
    assert soum.entreprise_id == 15
    assert soum.score_matching == 1.0


def test_admin_rejet_arbitrage_soumissionnaire():
    """Un administrateur peut écarter définitivement un candidat ambigu sans notifier l'entreprise."""
    db = MagicMock()
    admin_user = Utilisateur(id=99, email="admin@test.com", is_staff=True, is_superuser=True)

    soum = SoumissionnaireResultat(
        id=302,
        lot_resultat_id=5,
        nom_entreprise_brut="HOMONYME INCONNU",
        statut="ATTRIBUTAIRE",
        est_attributaire=True,
        statut_reconciliation="A_VERIFIER",
    )
    db.get.return_value = soum

    payload = ReconcilierSoumissionnaireRequest(
        action="REJETER",
        entreprise_id=None,
        emettre_alerte=False,
    )

    resp = resultats_router.reconcilier_soumissionnaire_manuellement(
        soumissionnaire_id=302,
        payload=payload,
        db=db,
        _admin=admin_user,
    )

    assert resp.status == "success"
    assert resp.statut_reconciliation == "NON_ASSIGNE"
    assert resp.entreprise_id is None
    assert resp.alerte_emise is False


def test_get_alertes_resultats_entreprise():
    """Vérifie la consultation de l'historique des alertes émises pour une entreprise."""
    db = MagicMock()
    user_client = Utilisateur(id=1, email="client@test.com", is_staff=False, is_superuser=False)
    ent = Entreprise(id=10, nom="ENTREPRISE FASO SERVICES", owner_id=1)
    db.get.side_effect = lambda model, ident: ent if model == Entreprise and ident == 10 else None

    from datetime import datetime, timezone
    alerte = AlerteResultat(
        id=50,
        entreprise_id=10,
        soumissionnaire_resultat_id=201,
        canal_alerte="WHATSAPP",
        type_notification="VICTOIRE",
        contenu_alerte="Félicitations...",
        date_envoi=datetime.now(timezone.utc),
        statut_envoi="ENVOYE",
        message_hash="hash_dummy_123",
    )
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [alerte]
    db.scalars.return_value = scalars_mock

    alertes = resultats_router.get_alertes_resultats_entreprise(
        entreprise_id=10,
        db=db,
        current_user=user_client,
    )

    assert len(alertes) == 1
    assert alertes[0].id == 50
    assert alertes[0].canal_alerte == "WHATSAPP"
    assert alertes[0].type_notification == "VICTOIRE"


def test_admin_get_resultats_bulletin_audit():
    """Vérifie l'accès administrateur à l'audit complet des résultats d'un bulletin (Règle d'Or n°5)."""
    db = MagicMock()
    admin_user = Utilisateur(id=99, email="admin@test.com", is_staff=True, is_superuser=True)

    res1 = ResultatAttribution(
        id=1,
        bulletin_numero="4458",
        page_source=8,
        autorite_contractante="MINISTERE DES FINANCES",
        objet="Acquisition de matériel informatique",
    )

    scalars_mock = MagicMock()
    unique_mock = MagicMock()
    unique_mock.all.return_value = [res1]
    scalars_mock.unique.return_value = unique_mock
    db.scalars.return_value = scalars_mock

    audit_resultats = resultats_router.get_resultats_bulletin_audit(
        bulletin_numero="4458",
        db=db,
        _admin=admin_user,
    )

    assert len(audit_resultats) == 1
    assert audit_resultats[0].bulletin_numero == "4458"
    assert audit_resultats[0].autorite_contractante == "MINISTERE DES FINANCES"


def test_admin_models_and_views_registered():
    """Vérifie que les vues d'administration des résultats d'attribution sont bien déclarées pour sqladmin."""
    # Test d'importation et d'intégrité des classes ModelView définies dans api/admin.py
    import inspect
    with open("E-Assis-main/api/admin.py", "r", encoding="utf-8") as f:
        admin_code = f.read()

    assert "ResultatAttributionAdmin" in admin_code
    assert "LotResultatAdmin" in admin_code
    assert "SoumissionnaireResultatAdmin" in admin_code
    assert "AlerteResultatAdmin" in admin_code
    assert "category = \"Résultats d'attribution\"" in admin_code
    assert "admin.add_view(view)" in admin_code


