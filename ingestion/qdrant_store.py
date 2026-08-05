import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingestion import config


def get_client() -> QdrantClient:
    return QdrantClient(url=config.QDRANT_URL)


def ensure_collection(client: QdrantClient, vector_size: int) -> None:
    if client.collection_exists(config.COLLECTION_NAME):
        return
    client.create_collection(
        collection_name=config.COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )


def delete_by_source(client: QdrantClient, source_file: str) -> None:
    if not client.collection_exists(config.COLLECTION_NAME):
        return
    client.delete(
        collection_name=config.COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="source_file", match=qmodels.MatchValue(value=source_file))]
            )
        ),
    )


def upsert_chunks(client: QdrantClient, chunks: list[dict], vectors: list[list[float]]) -> None:
    points = [
        qmodels.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=chunk)
        for chunk, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=config.COLLECTION_NAME, points=points)


def scroll_by_source(client: QdrantClient, source_file: str) -> list[dict]:
    """Tous les payloads des chunks d'un bulletin (pas de limite de points, pagine jusqu'a
    epuisement) - utilise pour l'extraction structuree et le matching, qui ont besoin de
    l'integralite d'un bulletin plutot que d'un top-K de recherche."""
    points: list[dict] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=config.COLLECTION_NAME,
            scroll_filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="source_file", match=qmodels.MatchValue(value=source_file))]
            ),
            limit=256,
            offset=offset,
            with_payload=True,
        )
        points.extend(p.payload for p in batch)
        if offset is None:
            break
    return points
