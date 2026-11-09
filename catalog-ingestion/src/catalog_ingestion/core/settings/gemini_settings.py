from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from catalog_ingestion.core.settings._env_config import EnvConfig


class GeminiSettings(BaseSettings):
    model_config = EnvConfig.for_prefix("GEMINI_")

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
