"""Tests unitaires et d'intégration pour le pipeline de notification des résultats (Étape 5).

Valide :
- Règle 1 : Déterminisme d'abord
- Règle 2 : Tolérance Zéro aux faux positifs (exclusion de A_VERIFIER et score < 0.85)
- Règle 3 : Idempotence absolue des pipelines (pas de double envoi d'alerte)
- Règle 4 : Préservation et réutilisation des briques (email_utils, whatsapp_client)
- Règle 5 : Traçabilité et auditabilité (bulletin, lot, montant, REX)
- Règle 6 : Gestion défensive des erreurs
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from api.services.resultats_notifier import (
    calculer_message_hash,
    formater_montant_fcfa,
    notifier_resultat_soumissionnaire,
    notifier_tous_resultats_bulletin,
)


class MockQuery:
    def __init__(self, data: list):
        self._data = list(data)

    def filter(self, *args, **kwargs):
        filtered = self._data
        for cond in args:
            if callable(cond):
                filtered = [item for item in filtered if cond(item)]
        return MockQuery(filtered)

    def join(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._data)

    def first(self):
        return self._data[0] if self._data else None

    def distinct(self):
        return self


class MockSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = False
        self.entreprises = []
        self.alertes = []
        self.resultats = []

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, AlerteResultat):
            self.alertes.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed = True

    def close(self):
        pass

    def query(self, model):
        from api.models.entreprise import Entreprise
        if model == Entreprise:
            return MockQuery(self.entreprises)
        if model == AlerteResultat:
            return MockQuery(self.alertes)
        if model == ResultatAttribution:
            return MockQuery(self.resultats)
        return MockQuery([])


class TestResultatsNotifier(unittest.TestCase):
    def setUp(self):
        self.db = MockSession()

        # Entreprise test
        self.entreprise = SimpleNamespace(
            id=42,
            nom="FASO INFORMATIQUE SARL",
            email="contact@faso-info.bf",
            telephone="+22670000001",
            langue_alertes="fr",
            owner_id=1,
        )
        self.db.entreprises.append(self.entreprise)

        # Résultat, Lot et Soumissionnaires
        self.resultat = ResultatAttribution(
            id=10,
            bulletin_numero="4458",
            page_source=12,
            autorite_contractante="Ministère de la Santé",
            reference_dossier="T_DMP_2024_01",
            objet="Acquisition de serveurs et d'équipements réseaux",
            date_attribution=datetime(2024, 6, 15, tzinfo=timezone.utc),
        )

        self.lot1 = LotResultat(
            id=101,
            resultat_attribution_id=10,
            numero_lot="1",
            intitule_lot="Fourniture de serveurs rackables",
            statut="ATTRIBUE",
        )
        self.lot1.resultat_attribution = self.resultat
        self.resultat.lots = [self.lot1]

        # Soumissionnaire 1 : Vainqueur
        self.soum_gagnant = SoumissionnaireResultat(
            id=501,
            lot_resultat_id=101,
            nom_entreprise_brut="FASO INFORMATIQUE SARL",
            entreprise_id=42,
            statut_reconciliation="EXACT",
            score_matching=1.0,
            methode_matching="IFU_EXACT",
            est_attributaire=True,
            statut="ATTRIBUTAIRE",
            montant_lu=Decimal("25000000"),
            montant_corrige=Decimal("25000000"),
            delai_execution="45 jours",
        )
        self.soum_gagnant.lot_resultat = self.lot1

        # Soumissionnaire 2 : Écarté avec motif REX
        self.soum_perdant = SoumissionnaireResultat(
            id=502,
            lot_resultat_id=101,
            nom_entreprise_brut="FASO INFORMATIQUE SARL",
            entreprise_id=42,
            statut_reconciliation="PROBABLE",
            score_matching=0.92,
            methode_matching="TRIGRAM",
            est_attributaire=False,
            statut="ECARTE",
            montant_lu=Decimal("28000000"),
            montant_corrige=Decimal("28000000"),
            motif_rejet="Offre financière supérieure à l'estimation",
        )
        self.soum_perdant.lot_resultat = self.lot1

        # Autre soumissionnaire : Douteux / A_VERIFIER
        self.soum_douteux = SoumissionnaireResultat(
            id=503,
            lot_resultat_id=101,
            nom_entreprise_brut="FASO QUELQUE CHOSE",
            entreprise_id=42,
            statut_reconciliation="A_VERIFIER",
            score_matching=0.72,
            methode_matching="TRIGRAM",
            est_attributaire=True,
            statut="ATTRIBUTAIRE",
        )
        self.soum_douteux.lot_resultat = self.lot1

        self.lot1.soumissionnaires = [self.soum_gagnant, self.soum_perdant]

    def test_calculer_message_hash_deterministe(self):
        """Règle 3 : Le hash doit être déterministe pour garantir l'idempotence."""
        h1 = calculer_message_hash(42, 501, "ATTRIBUTION_VICTOIRE", "4458", 101)
        h2 = calculer_message_hash(42, 501, "ATTRIBUTION_VICTOIRE", "4458", 101)
        h3 = calculer_message_hash(42, 501, "ATTRIBUTION_ECHEC", "4458", 101)

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)  # SHA-256 hex digest

    def test_formater_montant_fcfa(self):
        """Formatage lisible et soigné des montants FCFA."""
        self.assertEqual(formater_montant_fcfa(Decimal("25000000")), "25 000 000 FCFA")
        self.assertEqual(formater_montant_fcfa(None), "Montant non précisé")

    @patch("api.services.resultats_notifier.entreprise_est_eligible_alerte", return_value=True)
    def test_regle_2_tolerance_zero_faux_positifs(self, mock_eligible):
        """Règle 2 : Aucune alerte ne doit être émise si statut_reconciliation == 'A_VERIFIER'."""
        with patch("api.services.resultats_notifier.send_whatsapp_template") as mock_wa, \
             patch("api.services.resultats_notifier.send_resultat_victoire_email") as mock_mail:
            alerte, deja = notifier_resultat_soumissionnaire(
                self.db,
                self.soum_douteux,
                bulletin_numero="4458",
                page_number=12,
            )
            self.assertIsNone(alerte)
            self.assertFalse(deja)
            mock_wa.assert_not_called()
            mock_mail.assert_not_called()
            self.assertEqual(len(self.db.added), 0)

    @patch("api.services.resultats_notifier.entreprise_est_eligible_alerte", return_value=True)
    def test_notification_victoire_succes_multi_canal(self, mock_eligible):
        """Vérifie l'envoi WhatsApp + Email pour une victoire avec enregistrement AlerteResultat."""
        with patch("api.services.resultats_notifier.send_whatsapp_template") as mock_wa, \
             patch("api.services.resultats_notifier.send_resultat_victoire_email") as mock_mail:
            mock_wa.return_value = {"messages": [{"id": "wamid.123"}]}

            alerte, deja = notifier_resultat_soumissionnaire(
                self.db,
                self.soum_gagnant,
                bulletin_numero="4458",
                page_number=12,
            )

            self.assertIsNotNone(alerte)
            self.assertFalse(deja)
            self.assertEqual(alerte.type_notification, "ATTRIBUTION_VICTOIRE")
            self.assertEqual(alerte.statut_envoi, "SENT")
            self.assertEqual(alerte.canal_alerte, "whatsapp+email")
            self.assertIn("Félicitations", alerte.contenu_alerte)
            self.assertIn("FASO INFORMATIQUE SARL", alerte.contenu_alerte)
            self.assertIn("25 000 000 FCFA", alerte.contenu_alerte)

            # Vérifier l'appel WhatsApp
            mock_wa.assert_called_once()
            args, kwargs = mock_wa.call_args
            self.assertEqual(args[0], "+22670000001")
            self.assertIn("FASO INFORMATIQUE SARL", kwargs["parameters"])

            # Vérifier l'appel Email
            mock_mail.assert_called_once()
            mail_kwargs = mock_mail.call_args.kwargs
            self.assertEqual(mail_kwargs["user_email"], "contact@faso-info.bf")
            self.assertEqual(mail_kwargs["autorite_contractante"], "Ministère de la Santé")
            self.assertEqual(mail_kwargs["montant"], "25 000 000 FCFA")
            self.assertEqual(mail_kwargs["delai_execution"], "45 jours")

    @patch("api.services.resultats_notifier.entreprise_est_eligible_alerte", return_value=True)
    def test_regle_3_idempotence_absolue_pas_de_double_envoi(self, mock_eligible):
        """Règle 3 : Le rejeu du pipeline ne doit jamais réémettre une alerte déjà envoyée."""
        with patch("api.services.resultats_notifier.send_whatsapp_template") as mock_wa, \
             patch("api.services.resultats_notifier.send_resultat_victoire_email") as mock_mail:
            # 1er passage
            alerte1, deja1 = notifier_resultat_soumissionnaire(
                self.db,
                self.soum_gagnant,
                bulletin_numero="4458",
                page_number=12,
            )
            self.assertEqual(alerte1.statut_envoi, "SENT")
            self.assertFalse(deja1)
            self.assertEqual(mock_wa.call_count, 1)
            self.assertEqual(mock_mail.call_count, 1)

            # 2e passage avec la même alerte déjà présente dans la base
            mock_wa.reset_mock()
            mock_mail.reset_mock()

            alerte2, deja2 = notifier_resultat_soumissionnaire(
                self.db,
                self.soum_gagnant,
                bulletin_numero="4458",
                page_number=12,
            )
            self.assertEqual(alerte2, alerte1)
            self.assertTrue(deja2)
            # Zéro appel réseau supplémentaire !
            mock_wa.assert_not_called()
            mock_mail.assert_not_called()

    @patch("api.services.resultats_notifier.entreprise_est_eligible_alerte", return_value=True)
    def test_notification_echec_avec_rex(self, mock_eligible):
        """Vérifie la notification constructive d'échec / REX (motif de rejet inclus)."""
        with patch("api.services.resultats_notifier.send_whatsapp_template") as mock_wa, \
             patch("api.services.resultats_notifier.send_resultat_echec_email") as mock_mail:
            alerte, deja = notifier_resultat_soumissionnaire(
                self.db,
                self.soum_perdant,
                bulletin_numero="4458",
                page_number=12,
            )

            self.assertIsNotNone(alerte)
            self.assertFalse(deja)
            self.assertEqual(alerte.type_notification, "ATTRIBUTION_ECHEC")
            self.assertEqual(alerte.statut_envoi, "SENT")
            self.assertIn("Offre financière supérieure", alerte.contenu_alerte)

            # Vérifier l'appel email avec motif_rejet
            mock_mail.assert_called_once()
            mail_kwargs = mock_mail.call_args.kwargs
            self.assertEqual(mail_kwargs["user_email"], "contact@faso-info.bf")
            self.assertEqual(mail_kwargs["motif_rejet"], "Offre financière supérieure à l'estimation")

    @patch("api.services.resultats_notifier.entreprise_est_eligible_alerte", return_value=True)
    def test_regle_6_resilience_erreur_whatsapp_email_relais(self, mock_eligible):
        """Règle 6 : Si WhatsApp échoue, l'email assure la notification sans crasher."""
        from api.whatsapp_client import WhatsAppSendError

        with patch("api.services.resultats_notifier.send_whatsapp_template", side_effect=WhatsAppSendError("Meta API down")), \
             patch("api.services.resultats_notifier.send_resultat_victoire_email") as mock_mail:
            alerte, deja = notifier_resultat_soumissionnaire(
                self.db,
                self.soum_gagnant,
                bulletin_numero="4458",
                page_number=12,
            )

            self.assertIsNotNone(alerte)
            self.assertFalse(deja)
            self.assertEqual(alerte.statut_envoi, "SENT")
            self.assertEqual(alerte.canal_alerte, "email")
            mock_mail.assert_called_once()

    @patch("api.services.resultats_notifier.entreprise_est_eligible_alerte", return_value=True)
    def test_notifier_tous_resultats_bulletin_stats(self, mock_eligible):
        """Vérifie le balayage complet d'un bulletin et le calcul des statistiques."""
        self.db.resultats = [self.resultat]

        with patch("api.services.resultats_notifier.send_whatsapp_template"), \
             patch("api.services.resultats_notifier.send_resultat_victoire_email"), \
             patch("api.services.resultats_notifier.send_resultat_echec_email"):
            stats = notifier_tous_resultats_bulletin(
                self.db,
                bulletin_numero="4458",
                dry_run=False,
            )

            self.assertEqual(stats["resultats_traites"], 1)
            self.assertEqual(stats["victoires_envoyees"], 1)
            self.assertEqual(stats["echecs_envoyes"], 1)
            self.assertEqual(stats["echoues"], 0)


if __name__ == "__main__":
    unittest.main()
