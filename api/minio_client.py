from minio import Minio

from api.config import settings


def build_presign_client() -> Minio:
    # secure=minio_public_secure (False en local, MinIO sans TLS - True en production derriere un
    # reverse-proxy HTTPS, cf. api/config.py). region="us-east-1" (region par defaut d'une
    # instance MinIO standalone) : sans ce parametre, presigned_get_object() appelle en interne
    # GetBucketLocation pour resoudre la region, donc essaie de JOINDRE minio_public_endpoint - or
    # cet hote (localhost:9000) n'est reachable que depuis le navigateur, pas depuis ce conteneur
    # (son "localhost" a lui, sans MinIO dessus). Fixer la region evite tout appel reseau : la
    # generation d'URL presignee devient une pure signature locale.
    return Minio(
        settings.minio_public_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_public_secure,
        region="us-east-1",
    )


def build_internal_minio_client() -> Minio:
    """Client MinIO interne pour les opérations réseau dans le conteneur API (hote minio:9000)."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user or "admin",
        secret_key=settings.minio_root_password or "Password123",
        secure=False,
    )


def ensure_bucket_and_sync_local(object_name: str, local_candidates: list[str] | None = None) -> None:
    """Garantit l'existence du bucket et téléverse un fichier local candidat s'il est manquant dans MinIO."""
    try:
        client = build_internal_minio_client()
        bucket = settings.minio_bucket
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        # Vérifier si l'objet existe déjà
        try:
            client.stat_object(bucket, object_name)
            return
        except Exception:
            pass

        # Téléverser depuis un candidat local si présent
        if local_candidates:
            import os
            for path in local_candidates:
                if os.path.exists(path):
                    client.fput_object(bucket, object_name, path, content_type="application/pdf")
                    break
    except Exception:
        # Ne jamais faire crasher la génération de presigned URL
        pass

