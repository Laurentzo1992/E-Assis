import argparse

from ingestion import config, embed, qdrant_store


def search(query: str, top_k: int = 5):
    vector = embed.embed_texts([query])[0]
    client = qdrant_store.get_client()
    return client.query_points(collection_name=config.COLLECTION_NAME, query=vector, limit=top_k).points


def main() -> None:
    parser = argparse.ArgumentParser(description="Recherche semantique dans Qdrant")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    for r in search(args.query, args.top_k):
        payload = r.payload
        print(f"[score={r.score:.3f}] page {payload['page_number']} - {payload.get('section_title')}")
        print(payload["text"][:300])
        print("---")


if __name__ == "__main__":
    main()
