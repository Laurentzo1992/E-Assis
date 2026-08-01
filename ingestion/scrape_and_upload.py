"""Archive dans MinIO le dernier bulletin publie sur le site DGCMEF, si nouveau.

Idempotent : le numero de bulletin sert de cle d'objet MinIO (pdf/quotidien/{numero}.pdf), donc
relancer cette fonction quand rien de nouveau n'a ete publie ne retelecharge ni ne re-uploade
rien - c'est ce test d'existence qui garantit qu'on ne traite "que le nouveau".
"""

from minio.error import S3Error

from ingestion import config, scraper


def _object_name(numero: str) -> str:
    return f"pdf/quotidien/{numero}.pdf"


def _already_archived(client, object_name: str) -> bool:
    try:
        client.stat_object(config.MINIO_BUCKET, object_name)
        return True
    except S3Error:
        return False


def ingest_new_bulletin() -> dict | None:
    bulletin = scraper.latest_bulletin()
    object_name = _object_name(bulletin["numero"])

    client = config.build_minio_client()
    if _already_archived(client, object_name):
        return None

    pdf_bytes = scraper.download_pdf(bulletin["url"])
    config.upload_bytes(client, config.MINIO_BUCKET, object_name, pdf_bytes, "application/pdf")

    return {"numero": bulletin["numero"], "object_name": object_name, "url_source": bulletin["url"]}
