from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    """A product id found by one retrieval path, before hydration from PostgreSQL."""

    product_id: str
    score: float | None
    source: Literal["semantic", "structured"]
