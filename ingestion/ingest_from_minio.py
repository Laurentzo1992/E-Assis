import argparse
import tempfile
from pathlib import Path

from ingestion import config, ingest


def ingest_object(object_name: str) -> int:
    client = config.build_minio_client()
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / Path(object_name).name
        client.fget_object(config.MINIO_BUCKET, object_name, str(local_path))
        return ingest.ingest_pdf(str(local_path), source_id=object_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexe dans Qdrant un PDF deja archive dans MinIO")
    parser.add_argument("object_name")
    args = parser.parse_args()
    n = ingest_object(args.object_name)
    print(f"{n} chunks indexes depuis MinIO:{args.object_name}")


if __name__ == "__main__":
    main()
