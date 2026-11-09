from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from catalog_ingestion.core.settings._env_config import EnvConfig


class IngestSettings(BaseSettings):
    model_config = EnvConfig.for_prefix("INGEST_")

    input_path: Path = Path("../products.zip")
    concurrency: int = Field(default=4, ge=1, le=64)
    # A full run refuses (unless --force) to deactivate more than this share of the active products.
    max_deactivate_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
