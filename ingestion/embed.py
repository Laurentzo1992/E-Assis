from functools import lru_cache

from sentence_transformers import SentenceTransformer

from ingestion import config


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(config.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
