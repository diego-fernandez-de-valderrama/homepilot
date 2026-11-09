"""Semantic retrieval over the Qdrant collection built by `catalog-ingestion`.

Queries are embedded with the same `GeminiEmbedder` (model, dimension, RETRIEVAL_QUERY task type,
L2 normalization) that produced the indexed document vectors. Only product ids and scores leave
this package: the payload is never used as a source of truth.

- `SemanticIndex`: the protocol the retrieval service depends on.
- `QdrantIndex`: its Qdrant implementation.
"""

from smart_home_agent.repositories.semantic.qdrant_index import QdrantIndex
from smart_home_agent.repositories.semantic.semantic_index import SemanticIndex

__all__ = ["QdrantIndex", "SemanticIndex"]
