"""Stage 3, semantic discovery: Qdrant, fed from PostgreSQL. Import everything from here:

    from catalog_ingestion.indexing import GeminiEmbedder, QdrantRepository, RetrievalDocumentBuilder, ...

1. `RetrievalDocumentBuilder.build`: `EnrichedProduct` -> `RetrievalDocument` (English canonical names next to
   the German catalog terms; its `doc_hash` decides whether the product is re-embedded).
2. `GeminiEmbedder` (the `Embedder` protocol): RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY embeddings, L2-normalized.
3. `QdrantRepository`: points keyed by `point_id(product_id)` with the `QdrantPayloadSchema`; `IndexedState`
   tells what a point was built from; `search` returns `SearchHit`s. `QdrantCollection` creates the client and
   the collection with its payload indexes.

Qdrant is for discovery only: prices, compatibility and filtering decisions always come from PostgreSQL.
"""

from catalog_ingestion.indexing.collection_dimension_mismatch_error import CollectionDimensionMismatchError
from catalog_ingestion.indexing.embedder import Embedder
from catalog_ingestion.indexing.gemini_embedder import GeminiEmbedder
from catalog_ingestion.indexing.indexed_state import IndexedState
from catalog_ingestion.indexing.qdrant_collection import QdrantCollection
from catalog_ingestion.indexing.qdrant_repository import QdrantRepository
from catalog_ingestion.indexing.retrieval_document_builder import RetrievalDocumentBuilder
from catalog_ingestion.indexing.search_hit import SearchHit

__all__ = [
    "CollectionDimensionMismatchError",
    "Embedder",
    "GeminiEmbedder",
    "IndexedState",
    "QdrantCollection",
    "QdrantRepository",
    "RetrievalDocumentBuilder",
    "SearchHit",
]
