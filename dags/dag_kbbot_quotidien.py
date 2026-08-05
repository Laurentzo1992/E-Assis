"""Ingestion quotidienne des bulletins "Quotidien des marches publics" (DGCMEF Burkina Faso).

scrape_and_archive (ingestion/scrape_and_upload.py, taches legeres - requests/minio, tournent
dans l'image Airflow) redecouvre le dernier bulletin publie sur le site et l'archive dans MinIO,
sous une cle nommee par son numero (pdf/quotidien/{numero}.pdf) : c'est ce test d'existence dans
MinIO qui garantit qu'on ne traite jamais deux fois le meme bulletin, et qu'on ignore les
executions ou rien de nouveau n'a ete publie (le site ne publie pas tous les jours, ex. week-ends).

has_new_bulletin court-circuite la suite du DAG si aucun nouveau bulletin n'a ete trouve.

vectorize_bulletin lance l'image kbbot-ingest (poids ML - torch/sentence-transformers/pymupdf)
dans son propre conteneur via DockerOperator, plutot que d'installer ces dependances dans l'image
Airflow (meme raisonnement que dag_warehouse_load/dbt dans fasofoodalert-core : eviter les
conflits de dependances avec Airflow lui-meme).

extract_structured_data (api/scripts/extract_bulletin.py) et match_and_alert
(api/scripts/match_and_alert.py) tournent aussi dans l'image kbbot-ingest (deja equipee
torch/sentence-transformers/qdrant-client pour l'embedding) plutot que kbbot-api, pour eviter de
dupliquer ces ~2 Go de dependances ML dans une deuxieme image juste pour l'acces Postgres
(sqlalchemy/psycopg2, ajoutes legers a kbbot-ingest a la place). Les deux appellent Ollama
(llm_service) pour l'extraction/la redaction - service demarre a la demande, cf.
docker-compose.llm.yml.
"""

import os

import pendulum
from airflow.decorators import dag, task
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
from notifications import DEFAULT_ARGS as default_args

from ingestion.scrape_and_upload import ingest_new_bulletin

INGEST_IMAGE = "kbbot-ingest:local"
INGEST_NETWORK = "kbbot_backend"

# DockerOperator lance le conteneur directement via l'API Docker, sans passer par
# docker-compose : le "env_file: .env" du service "ingest" de docker-compose.yml ne s'applique
# pas ici, il faut donc repasser explicitement les identifiants MinIO deja injectes dans
# l'environnement du scheduler (docker-compose.airflow.yml) - sans ca, le conteneur retombe sur
# les identifiants par defaut de config.py et echoue en InvalidAccessKeyId (constate en reel).
INGEST_ENVIRONMENT = {
    "QDRANT_URL": "http://qdrant:6333",
    "VISION_OCR_URL": "http://vision-ocr:8000",
    "MINIO_ENDPOINT": "minio:9000",
    **{
        key: os.environ[key]
        for key in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "MINIO_BUCKET")
        if key in os.environ
    },
}

# extract_structured_data/match_and_alert : besoin de Postgres + Ollama en plus de Qdrant, pas de
# MinIO/vision-ocr (ils ne touchent jamais au PDF source, seulement aux chunks deja vectorises).
# OLLAMA_HOST est repasse depuis l'environnement (pas fixe en dur) : "http://ollama:11434" pour
# le service conteneurise de docker-compose.llm.yml, ou "http://host.docker.internal:11434" pour
# une instance Ollama deja native sur la machine (cas verifie en reel sur ce poste).
_ANALYSE_ENV_KEYS = (
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "JWT_SECRET_KEY", "GOOGLE_CLIENT_ID",
    "OLLAMA_HOST", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_API_VERSION",
    "WHATSAPP_TEMPLATE_NAME", "WHATSAPP_TEMPLATE_LANGUAGE", "WHATSAPP_DEFAULT_COUNTRY_CODE",
    "WHATSAPP_MIN_MATCH_SCORE",
)
ANALYSE_ENVIRONMENT = {
    "QDRANT_URL": "http://qdrant:6333",
    "DATABASE_URL": (
        "postgresql+psycopg2://{user}:{password}@postgres:5432/{db}".format(
            user=os.environ.get("POSTGRES_USER", ""),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            db=os.environ.get("POSTGRES_DB", ""),
        )
    ),
    **{key: os.environ[key] for key in _ANALYSE_ENV_KEYS if key in os.environ},
}


@dag(
    dag_id="dag_kbbot_quotidien",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=default_args,
    tags=["kbbot", "ingestion", "pdf"],
)
def dag_kbbot_quotidien():
    @task
    def scrape_and_archive() -> str | None:
        result = ingest_new_bulletin()
        return result["object_name"] if result else None

    @task.short_circuit
    def has_new_bulletin(object_name: str | None) -> bool:
        return object_name is not None

    vectorize_bulletin = DockerOperator(
        task_id="vectorize_bulletin",
        image=INGEST_IMAGE,
        command="ingestion.ingest_from_minio {{ ti.xcom_pull(task_ids='scrape_and_archive') }}",
        environment=INGEST_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        # Sans ce mount, DockerOperator (contrairement a "docker compose run", qui applique les
        # volumes de docker-compose.yml) demarre le conteneur sans le cache du modele
        # d'embeddings : chaque execution re-telecharge ~1.1 Go depuis HuggingFace (constate en
        # reel : premiere execution reelle a pris plus de 2 minutes rien que pour ca).
        mounts=[Mount(source="kbbot_ingest_model_cache", target="/root/.cache", type="volume")],
    )

    extract_structured_data = DockerOperator(
        task_id="extract_structured_data",
        image=INGEST_IMAGE,
        command="api.scripts.extract_bulletin {{ ti.xcom_pull(task_ids='scrape_and_archive') }}",
        environment=ANALYSE_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        # Ecrase l'execution_timeout de 15 min herite de DEFAULT_ARGS (dimensionne pour les taches
        # legeres de fasofoodalert-core, pas pour un LLM local) - constate en reel : un bulletin de
        # 181 sections avec mistral-nemo:12b a largement depasse 15 min et a ete tue en plein appel
        # Ollama (le SIGTERM de timeout a ensuite fait echouer le nettoyage du conteneur Docker,
        # cf. l'erreur "cannot remove container: container is running").
        execution_timeout=pendulum.duration(hours=2),
    )

    # retries=0 : une alerte manquee un jour sera rattrapee au prochain bulletin plutot que
    # spammer des tentatives de renvoi WhatsApp en cas d'erreur transitoire (meme raisonnement que
    # trigger_alertes dans dag_warehouse_load de fasofoodalert-core).
    match_and_alert = DockerOperator(
        task_id="match_and_alert",
        image=INGEST_IMAGE,
        command="api.scripts.match_and_alert {{ ti.xcom_pull(task_ids='scrape_and_archive') }}",
        environment=ANALYSE_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        retries=0,
        # cf. extract_structured_data : 15 min (DEFAULT_ARGS) est trop court des qu'il y a
        # suffisamment d'entreprises actives (un appel LLM de redaction par match trouve).
        execution_timeout=pendulum.duration(hours=1),
        # embed_texts() (profil entreprise) a besoin du meme cache de modele que vectorize_bulletin.
        mounts=[Mount(source="kbbot_ingest_model_cache", target="/root/.cache", type="volume")],
    )

    object_name = scrape_and_archive()
    has_new_bulletin(object_name) >> vectorize_bulletin >> extract_structured_data >> match_and_alert


dag_kbbot_quotidien()
