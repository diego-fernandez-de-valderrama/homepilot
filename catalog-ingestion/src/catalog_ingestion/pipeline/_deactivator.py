import logging

from catalog_ingestion.core import LogSetup
from catalog_ingestion.database import PostgresRepository
from catalog_ingestion.indexing import QdrantRepository
from catalog_ingestion.models import ProductState
from catalog_ingestion.pipeline.run_stats import RunStats
from catalog_ingestion.preparation import LoadResult

logger = logging.getLogger(__name__)


class Deactivator:
    """Products missing from a full run become inactive, and inactive products leave the index."""

    def __init__(self, postgres: PostgresRepository, qdrant: QdrantRepository | None, max_ratio: float) -> None:
        self._pg = postgres
        self._qdrant = qdrant
        self._max_ratio = max_ratio

    def deactivate_missing(
        self, loaded: LoadResult, states: dict[str, ProductState], force: bool, stats: RunStats
    ) -> None:
        """Marks products missing from a full, cleanly loaded input as inactive.

        An empty input or unreadable files could otherwise deactivate products that still exist, so the
        step is skipped then; a large share of removals needs --force.
        """
        unreadable = [error for error in loaded.errors if not error.duplicate]
        if not loaded.products or unreadable:
            logger.warning(
                "Deactivation skipped: the input is empty or has unreadable files",
                extra=LogSetup.fields(loaded=len(loaded.products), unreadable=len(unreadable)),
            )
            stats.set("deactivation_skipped", 1)
            return
        present = {raw.id for raw in loaded.products}
        active = [pid for pid, state in states.items() if state.active]
        missing = [pid for pid in active if pid not in present]
        if not force and len(missing) > self._max_ratio * len(active):
            logger.error(
                "Deactivation refused: too many products are missing from the input (use --force if intended)",
                extra=LogSetup.fields(missing=len(missing), active=len(active), max_ratio=self._max_ratio),
            )
            stats.set("deactivation_skipped", 1)
            stats.set("deactivation_refused", len(missing))
            return
        stats.set("postgres_deactivated", len(self._pg.deactivate_missing(sorted(present))))

    def delete_inactive_from_index(self, stats: RunStats) -> None:
        """Deletes the Qdrant points of every inactive product, not only of this run's removals, so a
        delete that failed before (after PostgreSQL already committed) is retried."""
        if self._qdrant is None:
            return
        inactive = self._pg.inactive_ids()
        if not inactive:
            return
        try:
            self._qdrant.delete(inactive)
        except Exception:
            logger.exception("Qdrant delete of inactive products failed; it is retried on the next run")
            stats.set("qdrant_delete_failed", len(inactive))
            return
        self._pg.clear_indexed(inactive)
        stats.set("qdrant_deleted_inactive", len(inactive))
