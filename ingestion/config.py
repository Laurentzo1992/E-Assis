import os
from io import BytesIO

from minio import Minio

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
VISION_OCR_URL = os.getenv("VISION_OCR_URL", "http://localhost:8002")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "kbbot_documents")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2")

# Seuil sous lequel une page est consideree scannee/image (texte natif quasi absent) et bascule
# sur l'OCR vision plutot que d'etre indexee vide.
OCR_MIN_CHARS = int(os.getenv("OCR_MIN_CHARS", "50"))

CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "1000"))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "Password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "kbbot")

DGCMEF_TAXONOMY_URL = os.getenv(
    "DGCMEF_TAXONOMY_URL", "https://www.dgcmef.gov.bf/fr/taxonomy/term/16"
)


def build_minio_client() -> Minio:
    # secure=False : MinIO tourne en local sans TLS
    return Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)


def upload_bytes(client: Minio, bucket_name: str, object_name: str, data: bytes, content_type: str) -> None:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
    client.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
