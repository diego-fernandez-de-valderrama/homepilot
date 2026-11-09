from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """Identifies model + dimension; a change forces re-embedding."""
        ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
