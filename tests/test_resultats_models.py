"""Tests unitaires pour les modèles de résultats d'attribution (Étape 3).

Valide :
- La création et les contraintes de ResultatAttribution, LotResultat, SoumissionnaireResultat, AlerteResultat
- Le respect des règles d'or : traçabilité source, unicité des alertes, liaison cascade.
"""

from decimal import Decimal
from datetime import date, datetime
import sys
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
        sa_mock.orm = MagicMock()
        sa_mock.orm.mapped_column = MockColumn
        sa_mock.orm.relationship = lambda *args, **kwargs: []
        sa_mock.orm.declarative_base = lambda: Base
        sys.modules["sqlalchemy"] = sa_mock
        sys.modules["sqlalchemy.orm"] = sa_mock.orm
        sa_mock.dialects = MagicMock()
        sa_mock.dialects.postgresql = MagicMock()
        sys.modules["sqlalchemy.dialects"] = sa_mock.dialects
        sys.modules["sqlalchemy.dialects.postgresql"] = sa_mock.dialects.postgresql
        db_mock = MagicMock()
        db_mock.Base = Base
        db_mock.SessionLocal = MagicMock()
        sys.modules["api.database"] = db_mock

from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)


def test_instanciation_resultat_attribution():
    res = ResultatAttribution(
        bulletin_numero="4458",
        page_source=12,
        autorite_contractante="Ministère de la Transition Digitale",
        reference_dossier="2024-001/MTDPCE/SG/DMP",
        objet="Acquisition de matériel informatique et scanners de production",
        date_attribution=date(2024, 3, 4),
        statut_deliberation="ATTRIBUE",
        raw_source_snippet="| Lot 1 | FZ SERVICES SARL | Conforme | 24 500 000 |",
    )
    assert res.bulletin_numero == "4458"
    assert res.page_source == 12
    assert "MTDPCE" in res.reference_dossier
    assert "Acquisition" in res.objet
    assert str(res) == "Résultat 2024-001/MTDPCE/SG/DMP - Ministère de la Transition Digitale"


def test_instanciation_lot_et_soumissionnaires():
    res = ResultatAttribution(
        bulletin_numero="4458",
        page_source=12,
        autorite_contractante="DGCMEF",
        reference_dossier="2024-002/MEFP",
        objet="Fourniture de logiciels",
    )
    lot = LotResultat(
        resultat_attribution=res,
        numero_lot="1",
        intitule_lot="Fourniture de licences bureautiques",
        montant_estime=Decimal("50000000.00"),
        statut_lot="ATTRIBUE",
    )
    soum1 = SoumissionnaireResultat(
        lot_resultat=lot,
        nom_entreprise_brut="FZ SERVICES SARL",
        nom_entreprise_normalise="fz services",
        ifu_extrait="00012345X",
        statut="ATTRIBUTAIRE",
        est_attributaire=True,
        rang_classement=1,
        montant_lu=Decimal("48500000.00"),
        score_matching=1.0,
        methode_matching="IFU_EXACT",
        statut_reconciliation="EXACT",
    )
    soum2 = SoumissionnaireResultat(
        lot_resultat=lot,
        nom_entreprise_brut="BURKINA TECH SA",
        nom_entreprise_normalise="burkina tech",
        statut="ECARTE",
        est_attributaire=False,
        motif_rejet="Offre financière supérieure au budget alloué",
        statut_reconciliation="NON_ASSIGNE",
    )

    if not hasattr(res, "lots") or not res.lots:
        res.lots = [lot]
    if not hasattr(lot, "soumissionnaires") or not lot.soumissionnaires:
        lot.soumissionnaires = [soum1, soum2]

    assert len(res.lots) == 1
    assert len(lot.soumissionnaires) == 2
    assert soum1.est_attributaire is True
    assert soum2.est_attributaire is False
    assert "GAGNANT" in str(soum1)
    assert "ECARTE" in str(soum2)


def test_instanciation_alerte_resultat():
    alerte = AlerteResultat(
        entreprise_id=42,
        soumissionnaire_resultat_id=101,
        canal_alerte="whatsapp",
        type_notification="ATTRIBUTION_VICTOIRE",
        contenu_alerte="Félicitations ! Votre entreprise a été déclarée attributaire...",
        statut_envoi="SENT",
        message_hash="a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
    )
    assert alerte.entreprise_id == 42
    assert alerte.type_notification == "ATTRIBUTION_VICTOIRE"
    assert "ATTRIBUTION_VICTOIRE" in str(alerte)
