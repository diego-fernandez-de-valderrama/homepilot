from pydantic import SecretStr
from pydantic_settings import BaseSettings

from catalog_ingestion.core.settings._env_config import EnvConfig


class QdrantSettings(BaseSettings):
    model_config = EnvConfig.for_prefix("QDRANT_")

    url: str = "http://localhost:6333"
    api_key: SecretStr | None = None
    collection: str = "products"
