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

rattraper_profils_modifies (api/scripts/rattraper_entreprises.py) est INDEPENDANTE de
has_new_bulletin : une entreprise qui met a jour ses domaines/secteurs (cf.
api/routers/entreprise.py, update_entreprise) doit etre rattrapee meme un jour sans nouveau
bulletin DGCMEF (ex. week-end) - la brancher derriere match_and_alert la ferait sauter par le
short-circuit des que rien de neuf n'est publie.

Pipeline Résultats d'Attribution (Règles d'Or n°1 à n°6) :
extract_resultats_attribution (api/scripts/extract_resultats.py) et alert_resultats_attribution
(api/scripts/alert_resultats.py) s'exécutent en BRANCHE PARALLÈLE dès qu'un nouveau bulletin est
détecté (has_new_bulletin). Déterminisme d'abord : l'analyse tabulaire géométrique s'effectue
directement sur le bulletin archivé dans MinIO sans attendre la vectorisation Qdrant des avis.
Idempotence absolue et tolérance zéro aux faux positifs : seules les entreprises réconciliées avec
certitude reçoivent les notifications de victoire ou de REX.
"""

import os

import pendulum
from airflow.decorators import dag, task
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount
from notifications import DEFAULT_ARGS as default_args

from ingestion.scrape_and_upload import ingest_new_bulletin

# INGEST_IMAGE repasse par l'environnement (pas fixe en dur) : "kbbot-ingest:local" en dev (build
# local, cf. docker-compose.yml), "ghcr.io/laurentzo1992/kbbot-ingest:latest" en prod (image
# publiee par la CI, cf. .github/workflows/build-and-push.yml et docker-compose.prod.yml) - a
# definir dans le .env du VPS, sinon le DAG tenterait de lancer une image qui n'existe pas la-bas.
INGEST_IMAGE = os.environ.get("INGEST_IMAGE", "kbbot-ingest:local")
INGEST_NETWORK = "kbbot_backend"

# DockerOperator lance le conteneur directement via l'API Docker, sans passer par
# docker-compose : le "env_file: .env" du service "ingest" de docker-compose.yml ne s'applique
# pas ici, il faut donc repasser explicitement les identifiants MinIO deja injectes dans
# l'environnement du scheduler (docker-compose.airflow.yml) - sans ca, le conteneur retombe sur
# les identifiants par defaut de config.py et echoue en InvalidAccessKeyId (constate en reel).
INGEST_ENVIRONMENT = {
    "QDRANT_URL": "http://qdrant:6333",
    "MINIO_ENDPOINT": "minio:9000",
    **{
        key: os.environ[key]
        for key in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "MINIO_BUCKET")
        if key in os.environ
    },
}

# extract_structured_data/match_and_alert/extract_resultats/alert_resultats : besoin de Postgres,
# MinIO, WhatsApp, Email et LLM (en fallback ciblé).
_ANALYSE_ENV_KEYS = (
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "JWT_SECRET_KEY", "GOOGLE_CLIENT_ID",
    "PROD", "GCP_SERVICE_ACCOUNT_JSON", "GEMINI_MODEL", "GCP_LOCATION", "GCP_PROJECT_ID",
    "OLLAMA_HOST", "LOCAL_LLM_MODEL",
    "MINIO_ENDPOINT", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "MINIO_BUCKET",
    "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_API_VERSION",
    "WHATSAPP_TEMPLATE_NAME", "WHATSAPP_TEMPLATE_RESULTAT_VICTOIRE", "WHATSAPP_TEMPLATE_RESULTAT_ECHEC",
    "WHATSAPP_TEMPLATE_LANGUAGE", "WHATSAPP_DEFAULT_COUNTRY_CODE",
    "WHATSAPP_MIN_MATCH_SCORE",
    "DEFAULT_FROM_EMAIL", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD",
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
    # Toutes les 4h (pas @daily) : DGCMEF ne publie pas forcement son bulletin avant minuit -
    # constate en reel le 14/08/2026, bulletin n°4466 publie apres le passage quotidien de minuit,
    # donc pas traite avant le lendemain (alertes retardees d'une journee entiere). Sans impact sur
    # la charge : scrape_and_archive detecte "rien de nouveau" via _already_archived en quelques
    # secondes (cf. has_new_bulletin) - la plupart des passages toutes les 4h se terminent donc
    # aussi vite qu'avant, seul un vrai nouveau bulletin declenche le pipeline complet.
    schedule="0 */4 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=default_args,
    # Garde-fou : un passage plus lent que 4h (VPS de prod partage, sans GPU, cf.
    # execution_timeout de extract_structured_data) ne doit jamais chevaucher le passage suivant -
    # deux DockerOperator lances en parallele sur le meme bulletin n'auraient pas double-traite
    # (scrape_and_archive court-circuite via _already_archived), mais consommeraient inutilement le
    # CPU deja limite pour rien.
    max_active_runs=1,
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
        # cf. l'erreur "cannot remove container: container is running"). 2h s'est lui-meme revele
        # trop court sur le VPS de prod (18/08/2026) : CPU partage avec d'autres sites herberges sur
        # la meme machine (pas de GPU), extraction constatee depassant largement 2h sur un bulletin
        # charge - meme symptome (409 Conflict a la suppression du conteneur), tache marquee en
        # echec alors que l'extraction continuait reellement en arriere-plan.
        execution_timeout=pendulum.duration(hours=8),
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
        # suffisamment d'entreprises actives (un appel LLM de redaction/verification par match
        # trouve) - relever aussi par prudence sur le meme constat CPU partage du VPS de prod
        # (18/08/2026), meme si cette tache n'a pas encore ete observee en timeout elle-meme.
        execution_timeout=pendulum.duration(hours=3),
        # embed_texts() (profil entreprise) a besoin du meme cache de modele que vectorize_bulletin.
        mounts=[Mount(source="kbbot_ingest_model_cache", target="/root/.cache", type="volume")],
    )

    # retries=0 : meme raisonnement que match_and_alert - un rattrapage manque un jour sera
    # retente au prochain passage quotidien (l'entreprise reste marquee profil_a_rattraper tant
    # qu'elle n'a pas ete traitee avec succes).
    rattraper_profils_modifies = DockerOperator(
        task_id="rattraper_profils_modifies",
        image=INGEST_IMAGE,
        command="api.scripts.rattraper_entreprises",
        environment=ANALYSE_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        retries=0,
        execution_timeout=pendulum.duration(hours=1),
        mounts=[Mount(source="kbbot_ingest_model_cache", target="/root/.cache", type="volume")],
    )

    # Pipeline Résultats d'Attribution (Règles d'Or n°1 à n°6) :
    # Branche parallèle déclenchée dès qu'un nouveau bulletin est archivé dans MinIO.
    # L'extraction tabulaire est déterministe et s'exécute directement sur le bulletin sans dépendre
    # de la vectorisation Qdrant des avis d'appels d'offres (Règle d'Or n°4 : préservation du flux existant).
    extract_resultats_attribution = DockerOperator(
        task_id="extract_resultats_attribution",
        image=INGEST_IMAGE,
        command="api.scripts.extract_resultats {{ ti.xcom_pull(task_ids='scrape_and_archive') }}",
        environment=ANALYSE_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        retries=0,
        execution_timeout=pendulum.duration(hours=2),
    )

    # retries=0 : Idempotence absolue (Règle d'Or n°3). En cas d'erreur de livraison ponctuelle,
    # les alertes déjà envoyées sont consignées avec hash SHA-256 et ne seront jamais dupliquées.
    alert_resultats_attribution = DockerOperator(
        task_id="alert_resultats_attribution",
        image=INGEST_IMAGE,
        command="api.scripts.alert_resultats {{ ti.xcom_pull(task_ids='scrape_and_archive') }}",
        environment=ANALYSE_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        retries=0,
        execution_timeout=pendulum.duration(hours=1),
    )

    # Pipeline Appels d'offres ciblés par Domaine (Règles d'Or n°1 à n°6) :
    # Découpage unitaire des avis dès la page de démarrage détectée au sommaire (page 2),
    # classification IA par domaine d'activité et alertes ciblées par domaine.
    extract_avis_appels_offres = DockerOperator(
        task_id="extract_avis_appels_offres",
        image=INGEST_IMAGE,
        command="api.scripts.extract_avis {{ ti.xcom_pull(task_ids='scrape_and_archive') }}",
        environment=ANALYSE_ENVIRONMENT,
        network_mode=INGEST_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
        retries=0,
        execution_timeout=pendulum.duration(hours=2),
    )

    object_name = scrape_and_archive()
    bulletin_present = has_new_bulletin(object_name)

    # Branche 1 : Détection et alertes sur les opportunités (avis de marchés & appels d'offres)
    bulletin_present >> extract_avis_appels_offres
    bulletin_present >> vectorize_bulletin >> extract_structured_data >> match_and_alert

    # Branche 2 : Extraction tabulaire géométrique et alertes de résultats d'attribution (Règle d'Or n°4)
    bulletin_present >> extract_resultats_attribution >> alert_resultats_attribution

    # Tâche indépendante de rattrapage des profils modifiés
    rattraper_profils_modifies


dag_kbbot_quotidien()
