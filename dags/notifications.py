"""Notification d'echec, partagee par tous les DAGs de dags/.

Toujours journalise en ERROR (visible dans les logs de tache Airflow et dans l'UI, donc fonctionne
sans aucune configuration). Envoie en plus sur Slack si SLACK_WEBHOOK_URL est definie - juste
`requests` (deja present), pas de dependance au provider Slack.
"""

import logging
import os

import pendulum
import requests

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

logger = logging.getLogger(__name__)


def notify_failure(context: dict) -> None:
    task_instance = context["task_instance"]
    dag_id = task_instance.dag_id
    task_id = task_instance.task_id
    execution_date = context.get("logical_date") or context.get("execution_date")
    exception = context.get("exception")
    log_url = task_instance.log_url

    message = f"[ECHEC AIRFLOW] {dag_id}.{task_id} (execution: {execution_date}) - {exception}\nLogs : {log_url}"

    logger.error(message)

    if not SLACK_WEBHOOK_URL:
        return

    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    except requests.RequestException:
        logger.exception("Echec de l'envoi de la notification Slack")


DEFAULT_ARGS = {
    "retries": 2,
    "retry_delay": pendulum.duration(minutes=5),
    "on_failure_callback": notify_failure,
    "execution_timeout": pendulum.duration(minutes=15),
}
