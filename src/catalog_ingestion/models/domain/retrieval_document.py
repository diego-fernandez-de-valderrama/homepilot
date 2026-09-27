from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalDocument:
    """The text embedded for semantic retrieval of one product, and its hash (re-embed on change)."""

    product_id: str
    text: str
    doc_hash: str
