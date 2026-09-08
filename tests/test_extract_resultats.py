"""Tests d'intégration et d'idempotence pour l'extraction de résultats (Étape 4).

Valide :
- Règle 1 : Déterminisme d'abord, IA en complément
- Règle 2 : Tolérance zéro aux faux positifs (Entity Resolution intégrée)
- Règle 3 : Idempotence absolue des pipelines (pas de doublons)
- Règle 5 : Traçabilité et liaison aux sources (bulletin, page, snippets).
"""

import sys
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
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
                self.name = ""

            def __set_name__(self, owner, name):
                self.name = name

            def __eq__(self, other):
                name = self.name
                return lambda item: getattr(item, name, None) == other

            def __ne__(self, other):
                name = self.name
                return lambda item: getattr(item, name, None) != other

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
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from api.scripts.extract_resultats import sauvegarder_resultat_complet
from api.services.entity_resolution import EntityResolver
from api.services.tabular_resultats_parser import (
    LotResultatDTO,
    ResultatExtractionDTO,
    SoumissionnaireDTO,
)


class InMemoryDB:
    """Mock léger de session SQLAlchemy pour tester l'idempotence sans dépendre d'un Postgres actif."""

    def __init__(self, initial_entreprises=None):
        self.resultats = []
        self.lots = []
        self.soumissionnaires = []
        self.entreprises = initial_entreprises or []
        self._next_id = 1

    def add(self, obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = self._next_id
            self._next_id += 1
        if isinstance(obj, ResultatAttribution) and obj not in self.resultats:
            self.resultats.append(obj)
        elif isinstance(obj, LotResultat) and obj not in self.lots:
            self.lots.append(obj)
        elif isinstance(obj, SoumissionnaireResultat) and obj not in self.soumissionnaires:
            self.soumissionnaires.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def query(self, model):
        db = self

        class MockQuery:
            def __init__(self, items):
                self.items = items

            def filter(self, *criteria):
                filtered = list(self.items)
                for crit in criteria:
                    if callable(crit):
                        filtered = [x for x in filtered if crit(x)]
                return MockQuery(filtered)

            def first(self):
                return self.items[0] if self.items else None

            def all(self):
                return self.items

        if model == ResultatAttribution:
            return MockQuery(self.resultats)
        elif model == LotResultat:
            return MockQuery(self.lots)
        elif model == SoumissionnaireResultat:
            return MockQuery(self.soumissionnaires)
        else:
            return MockQuery(self.entreprises)


def test_sauvegarde_resultat_idempotence_et_reconciliation():
    e_inscrite = SimpleNamespace(
        id=101,
        nom="FZ SERVICES SARL",
        numero_identification="00012345X",
        rccm="BF-OUA-2020-B-111",
    )
    db = InMemoryDB(initial_entreprises=[e_inscrite])
    resolver = EntityResolver(db)

    dto = ResultatExtractionDTO(
        autorite_contractante="Ministère de la Transition Digitale",
        reference_dossier="2024-001/MTDPCE/SG/DMP",
        objet="Acquisition de matériel informatique",
        date_attribution=date(2024, 3, 4),
        statut_deliberation="ATTRIBUE",
        lots=[
            LotResultatDTO(
                numero_lot="1",
                intitule_lot="Fourniture d'ordinateurs portables",
                montant_estime=Decimal("30000000.00"),
                statut_lot="ATTRIBUE",
                soumissionnaires=[
                    SoumissionnaireDTO(
                        nom_entreprise_brut="FZ SERVICES SARL",
                        nom_entreprise_normalise="fz services",
                        ifu="00012345X",
                        est_attributaire=True,
                        statut="ATTRIBUTAIRE",
                        montant_lu=Decimal("24500000.00"),
                        montant_corrige=Decimal("24500000.00"),
                    ),
                    SoumissionnaireDTO(
                        nom_entreprise_brut="BURKINA TECH SA",
                        nom_entreprise_normalise="burkina tech",
                        est_attributaire=False,
                        statut="ECARTE",
                        motif_rejet="Offre financière trop élevée",
                    ),
                ],
            )
        ],
        methode_extraction="DETERMINISTE",
        snippet_source="Extrait de délibération",
    )

    # 1er passage
    res1 = sauvegarder_resultat_complet(
        db,
        dto,
        bulletin_numero="4458",
        page_source=12,
        resolver=resolver,
    )
    assert len(db.resultats) == 1
    assert len(db.lots) == 1
    assert len(db.soumissionnaires) == 2

    # Vérification attribution FZ SERVICES (reconnu avec certitude)
    soum_fz = next(s for s in db.soumissionnaires if s.nom_entreprise_brut == "FZ SERVICES SARL")
    assert soum_fz.entreprise_id == 101
    assert soum_fz.est_attributaire is True
    assert soum_fz.statut_reconciliation == "EXACT"

    # Vérification entreprise écartée BURKINA TECH
    soum_bt = next(s for s in db.soumissionnaires if s.nom_entreprise_brut == "BURKINA TECH SA")
    assert soum_bt.entreprise_id is None
    assert soum_bt.est_attributaire is False
    assert soum_bt.motif_rejet == "Offre financière trop élevée"

    # 2ème passage (test d'idempotence Règle n°3)
    res2 = sauvegarder_resultat_complet(
        db,
        dto,
        bulletin_numero="4458",
        page_source=12,
        resolver=resolver,
    )
    assert len(db.resultats) == 1
    assert len(db.lots) == 1
    assert len(db.soumissionnaires) == 2
