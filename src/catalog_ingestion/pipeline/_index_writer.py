import logging
from collections.abc import Callable
from itertools import batched

from catalog_ingestion.core import LogSetup
from catalog_ingestion.database import PostgresRepository
from catalog_ingestion.indexing import Embedder, QdrantRepository
from catalog_ingestion.models import EnrichedProduct, QdrantPayloadMapper, QdrantPayloadSchema, RetrievalDocument
from catalog_ingestion.pipeline.embedding_model_mismatch_error import EmbeddingModelMismatchError
from catalog_ingestion.pipeline.progress_sink import ProgressSink
from catalog_ingestion.pipeline.run_stats import RunStats

logger = logging.getLogger(__name__)


class IndexWriter:
    """Embeds retrieval documents and writes them to Qdrant, skipping points that are already up to date
    (same doc hash and embedding model); a payload-only change is written without re-embedding."""

    EMBED_BATCH = 50

    def __init__(
        self,
        postgres: PostgresRepository,
        qdrant: QdrantRepository | None,
        embedder: Embedder | None,
        progress: ProgressSink,
    ) -> None:
        self._pg = postgres
        self._qdrant = qdrant
        self._embedder = embedder
        self._progress = progress

    def check_model(self, is_full_run: bool) -> None:
        """A partial run only re-embeds its own products, so after an embedding model change it would
        leave vectors of two models in one collection: it is refused until `reindex` has run."""
        if is_full_run or self._qdrant is None or self._embedder is None:
            return
        other = self._qdrant.count_other_models(self._embedder.model_id)
        if other:
            raise EmbeddingModelMismatchError(
                f"{other} Qdrant points were embedded with another model than {self._embedder.model_id}. "
                "Run `catalog-ingestion reindex` (or a full `ingest`) before a partial run."
            )

    def index(self, documents: list[tuple[EnrichedProduct, RetrievalDocument]], force: bool, stats: RunStats) -> None:
        if self._qdrant is None or self._embedder is None:
            stats.set("qdrant_skipped_no_embedder", len(documents))
            logger.warning("Embedding/Qdrant stage skipped: no embedder configured (GEMINI_API_KEY missing?)")
            return
        model_id = self._embedder.model_id
        indexed = {} if force else self._qdrant.indexed_states([doc.product_id for _, doc in documents])
        pending: list[tuple[EnrichedProduct, RetrievalDocument]] = []
        payload_only: list[QdrantPayloadSchema] = []
        for enriched, doc in documents:
            state = indexed.get(doc.product_id)
            if state is None or state.doc_hash != doc.doc_hash or state.embedding_model != model_id:
                pending.append((enriched, doc))
                continue
            payload = QdrantPayloadMapper.from_enriched(enriched, doc.doc_hash, model_id)
            if state.payload_hash != payload.payload_hash:
                payload_only.append(payload)
        stats.set("qdrant_unchanged", len(documents) - len(pending) - len(payload_only))
        self._refresh_payloads(payload_only, stats)
        if not pending:
            stats.set("qdrant_indexed", 0)
            return

        self._progress.start("embed", len(pending))
        indexed_count = 0
        for number, batch in enumerate(batched(pending, self.EMBED_BATCH)):
            try:
                vectors = self._embedder.embed_documents([doc.text for _, doc in batch])
                self._store_vectors(list(batch), vectors, model_id)
                indexed_count += len(batch)
            except Exception:
                logger.exception(
                    "Embedding/Qdrant batch failed",
                    extra=LogSetup.fields(batch_start=number * self.EMBED_BATCH, size=len(batch)),
                )
                stats.inc("qdrant_failed", len(batch))
            self._progress.advance("embed", len(batch))
        self._progress.finish("embed")
        stats.set("qdrant_indexed", indexed_count)

    def rebuild(
        self, documents: list[tuple[EnrichedProduct, RetrievalDocument]], recreate: Callable[[], None], stats: RunStats
    ) -> None:
        """Embeds every document first and only then recreates the collection (through the callback), so a
        failure never leaves it empty."""
        if self._qdrant is None or self._embedder is None:
            raise RuntimeError("reindex --recreate needs Qdrant and an embedder")
        model_id = self._embedder.model_id
        self._progress.start("embed", len(documents))
        vectors: list[list[float]] = []
        for batch in batched(documents, self.EMBED_BATCH):
            vectors.extend(self._embedder.embed_documents([doc.text for _, doc in batch]))  # any error aborts
            self._progress.advance("embed", len(batch))
        self._progress.finish("embed")
        recreate()
        self._pg.clear_indexed([doc.product_id for _, doc in documents])
        for batch, batch_vectors in zip(
            batched(documents, self.EMBED_BATCH), batched(vectors, self.EMBED_BATCH), strict=True
        ):
            self._store_vectors(list(batch), list(batch_vectors), model_id)
        stats.set("qdrant_indexed", len(documents))

    def _refresh_payloads(self, payloads: list[QdrantPayloadSchema], stats: RunStats) -> None:
        """Payload-only changes (e.g. completeness level, image URL) are written without re-embedding."""
        if not payloads or self._qdrant is None:
            return
        try:
            self._qdrant.overwrite_payloads(payloads)
            stats.set("qdrant_payload_updated", len(payloads))
        except Exception:
            logger.exception("Qdrant payload update failed", extra=LogSetup.fields(size=len(payloads)))
            stats.inc("qdrant_failed", len(payloads))

    def _store_vectors(
        self, batch: list[tuple[EnrichedProduct, RetrievalDocument]], vectors: list[list[float]], model_id: str
    ) -> None:
        assert self._qdrant is not None
        self._qdrant.upsert(
            [
                (QdrantPayloadMapper.from_enriched(enriched, doc.doc_hash, model_id), vector)
                for (enriched, doc), vector in zip(batch, vectors, strict=True)
            ]
        )
        self._pg.mark_indexed([doc for _, doc in batch], model_id)
