from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexedState:
    """What a Qdrant point was built from: skips re-embedding (doc hash, model) and payload rewrites."""

    doc_hash: str | None
    embedding_model: str | None
    payload_hash: str | None = None
