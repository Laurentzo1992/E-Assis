import argparse

from ingestion import chunking, config, embed, extract, qdrant_store


def ingest_pdf(pdf_path: str, source_id: str | None = None) -> int:
    """source_id identifie le document dans Qdrant (dedoublonnage, citation) - distinct de
    pdf_path quand ce dernier est un fichier temporaire (ex. telecharge depuis MinIO par
    ingest_from_minio.py), auquel cas un chemin tmp/ different a chaque run casserait le
    dedoublonnage et rendrait la citation illisible."""
    source_id = source_id or pdf_path

    pages = extract.extract_pages(pdf_path)
    doc_number, doc_date = extract.parse_doc_metadata(pdf_path, pages)

    all_chunks = []
    for page in pages:
        page_chunks = chunking.chunk_page(page["text"], config.CHUNK_MAX_CHARS, config.CHUNK_OVERLAP_CHARS)
        for idx, chunk in enumerate(page_chunks):
            all_chunks.append(
                {
                    "source_file": source_id,
                    "doc_number": doc_number,
                    "doc_date": doc_date,
                    "page_number": page["page_number"],
                    "chunk_index": idx,
                    "section_title": chunk["section_title"],
                    "text": chunk["text"],
                }
            )

    if not all_chunks:
        return 0

    vectors = embed.embed_texts([c["text"] for c in all_chunks])
    client = qdrant_store.get_client()
    qdrant_store.ensure_collection(client, vector_size=len(vectors[0]))
    # Retire l'ancienne version du fichier avant d'inserer la nouvelle : les IDs de points sont
    # generes aleatoirement a chaque ingestion, donc sans ce nettoyage un simple re-import (PDF
    # corrige, re-run apres un bug de chunking) dupliquerait tous ses chunks au lieu de les remplacer.
    qdrant_store.delete_by_source(client, source_id)
    qdrant_store.upsert_chunks(client, all_chunks, vectors)
    return len(all_chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexe un PDF dans Qdrant")
    parser.add_argument("pdf_path")
    args = parser.parse_args()
    n = ingest_pdf(args.pdf_path)
    print(f"{n} chunks indexes depuis {args.pdf_path}")


if __name__ == "__main__":
    main()
