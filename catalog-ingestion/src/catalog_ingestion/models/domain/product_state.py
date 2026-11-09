from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProductState:
    """What PostgreSQL holds about a product before a run: hashes and the cached LLM output that
    decide whether its enrichment can be reused."""

    raw_hash: str
    document_hash: str
    enrichment_hash: str | None
    llm_output: dict[str, Any] | None
    enrichment_model: str | None
    prompt_version: str | None
    active: bool
