from minio.error import S3Error

from ingestion.scrape_and_upload import ingest_new_bulletin


class FakeMinioClient:
    def __init__(self, existing_objects=()):
        self.existing_objects = set(existing_objects)
        self.uploaded: list[str] = []

    def stat_object(self, bucket_name, object_name):
        if object_name not in self.existing_objects:
            raise S3Error("NoSuchKey", "not found", object_name, "req-id", "host-id", None)
        return {"object_name": object_name}

    def bucket_exists(self, bucket_name) -> bool:
        return True

    def make_bucket(self, bucket_name) -> None:
        pass

    def put_object(self, bucket_name, object_name, data, length, content_type):
        self.uploaded.append(object_name)


def test_ingest_new_bulletin_telecharge_et_archive_si_absent(monkeypatch):
    fake_client = FakeMinioClient(existing_objects=set())
    monkeypatch.setattr("ingestion.scrape_and_upload.config.build_minio_client", lambda: fake_client)
    monkeypatch.setattr(
        "ingestion.scrape_and_upload.scraper.latest_bulletin",
        lambda: {"numero": "4456", "url": "http://example.test/quotidien-4456.pdf"},
    )
    monkeypatch.setattr("ingestion.scrape_and_upload.scraper.download_pdf", lambda url: b"%PDF-fake")

    result = ingest_new_bulletin()

    assert result == {
        "numero": "4456",
        "object_name": "pdf/quotidien/4456.pdf",
        "url_source": "http://example.test/quotidien-4456.pdf",
    }
    assert fake_client.uploaded == ["pdf/quotidien/4456.pdf"]


def test_ingest_new_bulletin_ne_retelecharge_rien_si_deja_archive(monkeypatch):
    fake_client = FakeMinioClient(existing_objects={"pdf/quotidien/4456.pdf"})
    monkeypatch.setattr("ingestion.scrape_and_upload.config.build_minio_client", lambda: fake_client)
    monkeypatch.setattr(
        "ingestion.scrape_and_upload.scraper.latest_bulletin",
        lambda: {"numero": "4456", "url": "http://example.test/quotidien-4456.pdf"},
    )

    def _fail_if_called(url):
        raise AssertionError("download_pdf ne doit pas etre appele pour un bulletin deja archive")

    monkeypatch.setattr("ingestion.scrape_and_upload.scraper.download_pdf", _fail_if_called)

    result = ingest_new_bulletin()

    assert result is None
    assert fake_client.uploaded == []
