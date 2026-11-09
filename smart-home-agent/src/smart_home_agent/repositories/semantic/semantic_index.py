from collections.abc import Sequence
from typing import Protocol

from smart_home_agent.models import SearchCandidate


class SemanticIndex(Protocol):
    """What the retrieval service needs from the vector index."""

    def embed(self, text: str) -> list[float]: ...

    def search(self, vector: list[float], category: str | None, limit: int) -> list[SearchCandidate]: ...

    def score(self, vector: list[float], product_ids: Sequence[str]) -> dict[str, float]: ...
