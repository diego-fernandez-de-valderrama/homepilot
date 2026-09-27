from dataclasses import dataclass
from pathlib import Path

from catalog_ingestion.enrichment import EnrichmentPolicy


@dataclass(frozen=True, slots=True)
class IngestOptions:
    input_path: Path
    force: bool = False
    skip_web: bool = False
    skip_llm: bool = False
    refresh_web: bool = False
    only_products: tuple[str, ...] = ()
    limit: int | None = None
    concurrency: int = 4

    @property
    def is_full_run(self) -> bool:
        return not self.only_products and self.limit is None

    @property
    def enrichment_policy(self) -> EnrichmentPolicy:
        return EnrichmentPolicy(
            force=self.force, skip_web=self.skip_web, skip_llm=self.skip_llm, refresh_web=self.refresh_web
        )
