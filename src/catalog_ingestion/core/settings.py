"""Application settings loaded from environment variables and an optional `.env` file.

Each concern has its own settings class with a dedicated env prefix. `AppSettings`
composes them and is created once through `get_settings()`, then injected into
components by constructor.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ENV_FILE = ".env"


def _config(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class GeminiSettings(BaseSettings):
    model_config = _config("GEMINI_")

    api_key: SecretStr | None = None
    model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = Field(default=768, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    # Client-side pacing. Unset = no pacing. Free tier: set just below the per-minute quota (e.g. 14 for 15 RPM).
    requests_per_minute: int | None = Field(default=None, gt=0)
    embedding_requests_per_minute: int | None = Field(default=None, gt=0)
    max_retries: int = Field(default=8, ge=1)

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None and bool(self.api_key.get_secret_value())


class PostgresSettings(BaseSettings):
    model_config = _config("POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    db: str = "catalog"
    user: str = "catalog"
    password: SecretStr = SecretStr("catalog")

    @property
    def url(self) -> URL:
        """SQLAlchemy URL (psycopg 3 driver). Special characters in the password are escaped."""
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )


class QdrantSettings(BaseSettings):
    model_config = _config("QDRANT_")

    url: str = "http://localhost:6333"
    api_key: SecretStr | None = None
    collection: str = "products"


class WebSettings(BaseSettings):
    model_config = _config("WEB_")

    enabled: bool = True
    timeout_seconds: float = Field(default=15.0, gt=0)
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    max_text_chars: int = Field(default=20_000, gt=0)


class IngestSettings(BaseSettings):
    model_config = _config("INGEST_")

    input_path: Path = Path("../products.zip")
    concurrency: int = Field(default=4, ge=1, le=64)
    # A full run refuses (unless --force) to deactivate more than this share of the active products.
    max_deactivate_ratio: float = Field(default=0.2, ge=0.0, le=1.0)


class AppSettings(BaseModel):
    gemini: GeminiSettings
    postgres: PostgresSettings
    qdrant: QdrantSettings
    web: WebSettings
    ingest: IngestSettings

    @classmethod
    def load(cls) -> "AppSettings":
        return cls(
            gemini=GeminiSettings(),
            postgres=PostgresSettings(),
            qdrant=QdrantSettings(),
            web=WebSettings(),
            ingest=IngestSettings(),
        )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings.load()
