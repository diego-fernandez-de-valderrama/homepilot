from pydantic import SecretStr

from catalog_ingestion.core import AppSettings, GeminiSettings, PostgresSettings


def test_env_prefixes_and_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    monkeypatch.setenv("GEMINI_EMBEDDING_DIM", "1536")
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    monkeypatch.setenv("QDRANT_COLLECTION", "catalog_v2")
    monkeypatch.setenv("INGEST_CONCURRENCY", "8")

    settings = AppSettings.load()

    assert isinstance(settings.gemini.api_key, SecretStr)
    assert "secret-key" not in repr(settings.gemini)
    assert settings.gemini.is_configured
    assert settings.gemini.embedding_dim == 1536
    assert settings.postgres.host == "db.internal"
    url = settings.postgres.url
    assert (url.drivername, url.host, url.password) == ("postgresql+psycopg", "db.internal", "pw")
    assert "pw" not in str(url)  # rendered URLs hide the password
    assert settings.qdrant.collection == "catalog_v2"
    assert settings.ingest.concurrency == 8


def test_missing_api_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not GeminiSettings(_env_file=None).is_configured


def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_DB=from_file\n")
    assert PostgresSettings(_env_file=env_file).db == "from_file"
