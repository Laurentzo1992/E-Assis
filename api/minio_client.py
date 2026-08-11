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
