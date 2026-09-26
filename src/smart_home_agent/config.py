"""Settings for the agent service.

Infrastructure settings (Gemini, PostgreSQL, Qdrant) are the classes from
`catalog_ingestion.core.settings`, so both services read the same GEMINI_*, POSTGRES_* and
QDRANT_* variables. Only agent-specific options live here, under the AGENT_ prefix.
"""

from dataclasses import dataclass
from functools import lru_cache

from catalog_ingestion.core.settings import GeminiSettings, PostgresSettings, QdrantSettings
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model: str = "gemini-2.5-flash"  # chat/orchestration model (GEMINI_MODEL stays the enrichment model)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    app_name: str = "homepilot"
    # Candidates pulled from each retrieval path (semantic and structured) before hard filtering.
    candidate_pool: int = Field(default=50, ge=5, le=500)
    # An upsell alternative must reach this share of the best match's semantic relevance.
    upsell_min_relevance: float = Field(default=0.75, ge=0.0, le=1.0)


@dataclass(frozen=True, slots=True)
class Settings:
    agent: AgentSettings
    gemini: GeminiSettings
    postgres: PostgresSettings
    qdrant: QdrantSettings

    @classmethod
    def load(cls) -> "Settings":
        return cls(agent=AgentSettings(), gemini=GeminiSettings(), postgres=PostgresSettings(), qdrant=QdrantSettings())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()
