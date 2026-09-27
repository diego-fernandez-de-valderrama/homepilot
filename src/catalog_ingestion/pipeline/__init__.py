"""Stage orchestration: `IngestionPipeline` runs `ingest` and `reindex` over the stage packages.
Import everything from here:

    from catalog_ingestion.pipeline import IngestionPipeline, IngestOptions, RunStats, ...

`ingest(IngestOptions)`:
1. `preparation`: load products.zip, `ProductPreparer.prepare` each selected product;
2. `enrichment`: `ProductEnricher.enrich` in a thread pool (web, LLM, validation);
3. private `_product_recorder`: on the main thread, each result goes to PostgreSQL (product, web page cache,
   retrieval document);
4. private `_deactivator`: a full run marks missing products inactive (skipped for empty or unreadable input,
   refused above `max_deactivate_ratio` without `--force`) and deletes inactive products from Qdrant;
5. private `_index_writer`: embeds changed documents into Qdrant (payload-only changes without re-embedding).
   A partial run is refused (`EmbeddingModelMismatchError`) while Qdrant holds points of another model.

`reindex` rebuilds documents and embeddings from PostgreSQL. Counters go to `RunStats`, progress to a
`ProgressSink` (`NullProgress` by default).
"""

from catalog_ingestion.pipeline.embedding_model_mismatch_error import EmbeddingModelMismatchError
from catalog_ingestion.pipeline.ingest_options import IngestOptions
from catalog_ingestion.pipeline.ingestion_pipeline import IngestionPipeline
from catalog_ingestion.pipeline.null_progress import NullProgress
from catalog_ingestion.pipeline.progress_sink import ProgressSink
from catalog_ingestion.pipeline.run_stats import RunStats

__all__ = [
    "EmbeddingModelMismatchError",
    "IngestOptions",
    "IngestionPipeline",
    "NullProgress",
    "ProgressSink",
    "RunStats",
]
