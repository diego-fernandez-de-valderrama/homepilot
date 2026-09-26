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

    # Semantic input guardrail (guardrail/): set AGENT_GUARDRAIL_ENABLED=false to switch it off entirely
    # (no prototype embedding at startup, every message goes straight to the agent as before).
    guardrail_enabled: bool = True
    # Minimum cosine similarity per category and minimum lead over the second category; below either
    # the decision is UNCERTAIN and the message is allowed. Calibrated with `guardrail-eval --sweep`.
    # Scale of the CLASSIFICATION embedding space (see README "Tuning study").
    guardrail_threshold_smart_home: float = Field(default=0.70, ge=0.0, le=1.0)
    guardrail_threshold_electrical: float = Field(default=0.78, ge=0.0, le=1.0)
    guardrail_threshold_off_topic: float = Field(default=0.66, ge=0.0, le=1.0)
    guardrail_threshold_prompt_injection: float = Field(default=0.70, ge=0.0, le=1.0)
    guardrail_margin: float = Field(default=0.005, ge=0.0, le=1.0)
    # OFF_TOPIC needs more evidence: short small talk ("hmm", "I'm Diego") is the costliest false block.
    guardrail_off_topic_margin: float = Field(default=0.01, ge=0.0, le=1.0)
    guardrail_off_topic_min_words: int = Field(default=3, ge=0)
    # Off-topic requests are not blocked at input by default: the agent's prompt redirects them and the output
    # check replaces off-topic answers. true = also answer confident OFF_TOPIC messages before the model.
    guardrail_input_off_topic: bool = False
    # Deterministic checks of the final answer (guardrail/output_check.py); AGENT_GUARDRAIL_OUTPUT_CHECK=false disables.
    guardrail_output_check: bool = True


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
