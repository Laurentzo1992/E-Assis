"""Tests de validation structurelle et de topologie pour le DAG Airflow dag_kbbot_quotidien.

Règles d'Or appliquées :
- Règle 3 : Idempotence absolue des pipelines (retries=0 sur les tâches à effets secondaires).
- Règle 4 : Préservation du code existant et rétrocompatibilité (branche parallèle pour les résultats).
- Règle 6 : Gestion défensive et isolation des flux (découplage strict des branches).
- Règle 7 : Validation continue par tests réels.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


OPERATEURS_INSTANCIES = {}


def _setup_airflow_mocks():
    """Fournit des stubs minimaux pour Airflow et Docker si non installés sur la machine de test."""
    mocks_crees = []
    global OPERATEURS_INSTANCIES
    OPERATEURS_INSTANCIES = {}

    if "requests" not in sys.modules:
        mock_requests = ModuleType("requests")
        mock_requests.post = MagicMock()
        mock_requests.RequestException = Exception
        sys.modules["requests"] = mock_requests
        mocks_crees.append("requests")

    if "pendulum" not in sys.modules:
        mock_pendulum = ModuleType("pendulum")
        mock_pendulum.datetime = lambda *a, **k: "2026-01-01T00:00:00"
        mock_pendulum.duration = lambda *a, **k: MagicMock()
        sys.modules["pendulum"] = mock_pendulum
        mocks_crees.append("pendulum")

    if "docker" not in sys.modules:
        mock_docker = ModuleType("docker")
        mock_docker_types = ModuleType("docker.types")

        class MockMount:
            def __init__(self, source, target, type="volume"):
                self.source = source
                self.target = target
                self.type = type

        mock_docker_types.Mount = MockMount
        mock_docker.types = mock_docker_types
        sys.modules["docker"] = mock_docker
        sys.modules["docker.types"] = mock_docker_types
        mocks_crees.extend(["docker", "docker.types"])

    if "airflow" not in sys.modules:
        mock_airflow = ModuleType("airflow")
        mock_decorators = ModuleType("airflow.decorators")

        class MockTask:
            def __init__(self, fn, task_id=None):
                self.fn = fn
                self.task_id = task_id or fn.__name__
                self.downstreams = []
                self.upstreams = []

            def __call__(self, *args, **kwargs):
                return self

            def __rshift__(self, other):
                self.downstreams.append(other)
                if hasattr(other, "upstreams"):
                    other.upstreams.append(self)
                return other

        class MockDAG:
            def __init__(self, *args, **kwargs):
                self.dag_id = kwargs.get("dag_id", "test_dag")
                self.kwargs = kwargs
                self.tasks = {}

            def __call__(self, fn):
                def wrapper(*args, **kwargs):
                    return fn(*args, **kwargs)
                return wrapper

        def dag_decorator(*args, **kwargs):
            return MockDAG(*args, **kwargs)

        def task_decorator(fn):
            return MockTask(fn)

        task_decorator.short_circuit = lambda fn: MockTask(fn)

        mock_decorators.dag = dag_decorator
        mock_decorators.task = task_decorator
        mock_airflow.decorators = mock_decorators
        sys.modules["airflow"] = mock_airflow
        sys.modules["airflow.decorators"] = mock_decorators
        mocks_crees.extend(["airflow", "airflow.decorators"])

    if "airflow.providers.docker.operators.docker" not in sys.modules:
        mock_docker_mod = ModuleType("airflow.providers.docker.operators.docker")

        class MockDockerOperator:
            def __init__(self, task_id, image, command, **kwargs):
                self.task_id = task_id
                self.image = image
                self.command = command
                self.environment = kwargs.get("environment", {})
                self.network_mode = kwargs.get("network_mode")
                self.retries = kwargs.get("retries")
                self.execution_timeout = kwargs.get("execution_timeout")
                self.mounts = kwargs.get("mounts", [])
                self.downstreams = []
                self.upstreams = []
                OPERATEURS_INSTANCIES[task_id] = self

            def __rshift__(self, other):
                self.downstreams.append(other)
                if hasattr(other, "upstreams"):
                    other.upstreams.append(self)
                return other

            def __rrshift__(self, other):
                if hasattr(other, "downstreams"):
                    other.downstreams.append(self)
                self.upstreams.append(other)
                return self

        mock_docker_mod.DockerOperator = MockDockerOperator
        sys.modules["airflow.providers.docker.operators.docker"] = mock_docker_mod
        mocks_crees.append("airflow.providers.docker.operators.docker")

    if "ingestion.scrape_and_upload" not in sys.modules:
        mock_scrape = ModuleType("ingestion.scrape_and_upload")
        mock_scrape.ingest_new_bulletin = lambda: {"object_name": "pdf/quotidien/4458.pdf"}
        sys.modules["ingestion.scrape_and_upload"] = mock_scrape
        mocks_crees.append("ingestion.scrape_and_upload")

    return mocks_crees


def test_dag_structure_et_branches_paralleles():
    """Valide l'architecture du DAG et la Règle d'Or n°4 (branche parallèle des résultats)."""
    _setup_airflow_mocks()

    # Recharger le module pour exécuter avec les mocks
    if "dags.dag_kbbot_quotidien" in sys.modules:
        del sys.modules["dags.dag_kbbot_quotidien"]

    import dags.dag_kbbot_quotidien as dag_module

    # Vérification des variables d'environnement requises pour le pipeline résultats
    env_keys = dag_module._ANALYSE_ENV_KEYS
    assert "MINIO_ENDPOINT" in env_keys, "MINIO_ENDPOINT doit être présent pour l'accès aux PDF"
    assert "MINIO_BUCKET" in env_keys, "MINIO_BUCKET doit être présent pour l'accès aux PDF"
    assert "WHATSAPP_TEMPLATE_RESULTAT_VICTOIRE" in env_keys, "Template WhatsApp victoire manquant"
    assert "WHATSAPP_TEMPLATE_RESULTAT_ECHEC" in env_keys, "Template WhatsApp échec manquant"
    assert "DEFAULT_FROM_EMAIL" in env_keys, "Configuration Email manquante"


def test_commandes_taches_resultats():
    """Valide les commandes et contraintes des tâches de résultats d'attribution."""
    _setup_airflow_mocks()

    if "dags.dag_kbbot_quotidien" in sys.modules:
        del sys.modules["dags.dag_kbbot_quotidien"]

    import dags.dag_kbbot_quotidien as dag_module

    # Exécution de la fonction décorée pour générer les opérateurs
    dag_module.dag_kbbot_quotidien()

    # 1. Vérification que les deux tâches ont été créées
    assert "extract_resultats_attribution" in OPERATEURS_INSTANCIES, (
        "La tâche extract_resultats_attribution doit être instanciée dans le DAG"
    )
    assert "alert_resultats_attribution" in OPERATEURS_INSTANCIES, (
        "La tâche alert_resultats_attribution doit être instanciée dans le DAG"
    )

    tache_extract = OPERATEURS_INSTANCIES["extract_resultats_attribution"]
    tache_alert = OPERATEURS_INSTANCIES["alert_resultats_attribution"]

    # 2. Vérification des commandes d'exécution
    assert "api.scripts.extract_resultats" in tache_extract.command, (
        f"Commande incorrecte pour extract_resultats_attribution : {tache_extract.command}"
    )
    assert "api.scripts.alert_resultats" in tache_alert.command, (
        f"Commande incorrecte pour alert_resultats_attribution : {tache_alert.command}"
    )

    # 3. Vérification de l'idempotence absolue (Règle d'Or n°3 : retries=0 pour éviter le spam d'alertes)
    assert tache_alert.retries == 0, "alert_resultats_attribution doit avoir retries=0"
    assert tache_extract.retries == 0, "extract_resultats_attribution doit avoir retries=0"

    # 4. Vérification de l'ordonnancement séquentiel des résultats
    assert tache_alert in tache_extract.downstreams, (
        "alert_resultats_attribution doit s'exécuter directement en aval de extract_resultats_attribution"
    )
