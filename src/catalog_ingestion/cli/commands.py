"""CLI commands. Components are built here and injected into the pipeline."""

import json
import logging
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from qdrant_client import models

from catalog_ingestion.cli.reporting import RichProgress, console, print_counts
from catalog_ingestion.core.logging import configure_logging
from catalog_ingestion.core.settings import AppSettings, get_settings
from catalog_ingestion.llm.client import GeminiClient, GeminiModelNotFoundError
from catalog_ingestion.llm.enricher import LLMEnricher
from catalog_ingestion.pipeline.orchestrator import IngestionPipeline, IngestOptions
from catalog_ingestion.quality.profile import profile_dataset
from catalog_ingestion.retrieval.embeddings import GeminiEmbedder
from catalog_ingestion.storage.postgres.engine import create_db_engine, create_session_factory, upgrade_to_head
from catalog_ingestion.storage.postgres.repository import PostgresRepository
from catalog_ingestion.storage.qdrant.collection import create_client, ensure_collection
from catalog_ingestion.storage.qdrant.repository import QdrantRepository
from catalog_ingestion.web.fetchers import (
    Fetcher,
    GeminiUrlContextFetcher,
    HttpxFetcher,
)
from catalog_ingestion.web.retriever import WebRetriever

logger = logging.getLogger(__name__)

InputOption = Annotated[
    Path | None, typer.Option("--input", "-i", help="Path to products.zip (default: INGEST_INPUT_PATH).")
]


def _gemini(settings: AppSettings) -> GeminiClient | None:
    if not settings.gemini.is_configured:
        logger.warning("GEMINI_API_KEY is not set: LLM enrichment, url_context fetching and embeddings are disabled")
        return None
    return GeminiClient(settings.gemini)


def _qdrant(settings: AppSettings, recreate: bool = False) -> QdrantRepository:
    client = create_client(settings.qdrant)
    ensure_collection(client, settings.qdrant.collection, settings.gemini.embedding_dim, recreate=recreate)
    return QdrantRepository(client, settings.qdrant.collection)


@contextmanager
def _postgres(settings: AppSettings, migrate: bool = False) -> Iterator[PostgresRepository]:
    """Repository bound to a fresh engine; `migrate` applies pending Alembic migrations first."""
    engine = create_db_engine(settings.postgres)
    try:
        if migrate:
            upgrade_to_head(engine)
        yield PostgresRepository(create_session_factory(engine))
    finally:
        engine.dispose()


def _resolve_input(path: Path | None, settings: AppSettings) -> Path:
    resolved = path or settings.ingest.input_path
    if not resolved.is_file():
        raise typer.BadParameter(f"input file not found: {resolved}", param_hint="--input")
    return resolved


def init() -> None:
    """Apply PostgreSQL migrations (Alembic) and create the Qdrant collection (idempotent)."""
    configure_logging()
    settings = get_settings()
    with _postgres(settings, migrate=True):
        pass
    _qdrant(settings)
    console.print(
        f"[green]Ready[/]: PostgreSQL migrated to head, Qdrant collection '{settings.qdrant.collection}' "
        f"(dim={settings.gemini.embedding_dim})."
    )


def ingest(
    input_path: InputOption = None,
    force: Annotated[bool, typer.Option(help="Ignore all caches: re-run LLM enrichment and re-embed.")] = False,
    skip_web: Annotated[bool, typer.Option(help="Do not fetch product pages (cached pages are still used).")] = False,
    skip_llm: Annotated[
        bool, typer.Option(help="Deterministic enrichment only (cached LLM output is still used).")
    ] = False,
    refresh_web: Annotated[bool, typer.Option(help="Re-fetch product pages even if cached.")] = False,
    only_product: Annotated[list[str] | None, typer.Option(help="Process only this product id (repeatable).")] = None,
    limit: Annotated[int | None, typer.Option(min=1, help="Process only the first N products.")] = None,
    concurrency: Annotated[int | None, typer.Option(min=1, max=64, help="Parallel web/LLM workers.")] = None,
) -> None:
    """Ingest products.zip into PostgreSQL and Qdrant (idempotent, incremental)."""
    configure_logging()
    settings = get_settings()
    options = IngestOptions(
        input_path=_resolve_input(input_path, settings),
        force=force,
        skip_web=skip_web,
        skip_llm=skip_llm,
        refresh_web=refresh_web,
        only_products=tuple(only_product or ()),
        limit=limit,
        concurrency=concurrency or settings.ingest.concurrency,
    )
    gemini = _gemini(settings)
    if gemini is not None:
        try:
            gemini.check_models()
        except GeminiModelNotFoundError as exc:
            console.print(f"[red]Configuration error:[/] {exc}")
            raise typer.Exit(code=2) from exc
    with ExitStack() as stack:
        postgres = stack.enter_context(_postgres(settings, migrate=True))

        fetchers: list[Fetcher] = []
        if settings.web.enabled and not skip_web:
            http = HttpxFetcher(settings.web)
            stack.callback(http.close)
            fetchers.append(http)
            if gemini is not None:
                fetchers.append(GeminiUrlContextFetcher(gemini, settings.web))

        progress = stack.enter_context(RichProgress())
        pipeline = IngestionPipeline(
            postgres=postgres,
            qdrant=_qdrant(settings),
            embedder=GeminiEmbedder(gemini, settings.gemini) if gemini else None,
            web=WebRetriever(fetchers) if fetchers else None,
            enricher=LLMEnricher(gemini, settings.gemini.temperature) if gemini and not skip_llm else None,
            model_name=settings.gemini.model,
            progress=progress,
            max_deactivate_ratio=settings.ingest.max_deactivate_ratio,
        )
        try:
            stats = pipeline.ingest(options)
        except KeyboardInterrupt:
            if gemini is not None:
                gemini.cancel()  # wake worker threads waiting on rate limits so the process exits now
            console.print(
                "\n[yellow]Interrupted.[/] Every product finished before the interruption is saved. "
                "Run `ingest` again to continue with the remaining ones."
            )
            raise typer.Exit(code=130) from None
    print_counts("Ingestion summary", stats.as_dict())


def reindex(
    force: Annotated[bool, typer.Option(help="Re-embed every product even if unchanged.")] = False,
    recreate: Annotated[bool, typer.Option(help="Drop and recreate the Qdrant collection first.")] = False,
) -> None:
    """Rebuild retrieval documents and embeddings from PostgreSQL (no web, no LLM calls)."""
    configure_logging()
    settings = get_settings()
    gemini = _gemini(settings)
    if gemini is None:
        raise typer.Exit(code=1)
    with _postgres(settings) as postgres, RichProgress() as progress:
        pipeline = IngestionPipeline(
            postgres=postgres,
            qdrant=_qdrant(settings, recreate=recreate),
            embedder=GeminiEmbedder(gemini, settings.gemini),
            web=None,
            enricher=None,
            model_name=settings.gemini.model,
            progress=progress,
        )
        stats = pipeline.reindex(force=force or recreate)
    print_counts("Reindex summary", stats.as_dict())


def analyze(input_path: InputOption = None) -> None:
    """Profile the dataset (no database needed)."""
    configure_logging()
    settings = get_settings()
    profile = profile_dataset(_resolve_input(input_path, settings))
    for name, counts in asdict(profile).items():
        print_counts(name.replace("_", " ").capitalize(), counts, humanize=name in ("counts", "completeness_levels"))


def search(
    query: Annotated[str, typer.Argument(help="Natural language query (English or German).")],
    limit: Annotated[int, typer.Option(min=1, max=50)] = 5,
    ecosystem: Annotated[str | None, typer.Option(help="Filter: canonical ecosystem, e.g. apple_home.")] = None,
    category: Annotated[str | None, typer.Option(help="Filter: category key, e.g. heating_control.")] = None,
    max_price: Annotated[float | None, typer.Option(help="Filter: maximum price in EUR.")] = None,
) -> None:
    """Semantic search smoke test against Qdrant (with optional payload filters)."""
    configure_logging()
    settings = get_settings()
    gemini = _gemini(settings)
    if gemini is None:
        raise typer.Exit(code=1)
    conditions: list[models.Condition] = []
    if ecosystem:
        conditions.append(models.FieldCondition(key="ecosystems", match=models.MatchValue(value=ecosystem)))
    if category:
        conditions.append(models.FieldCondition(key="category", match=models.MatchValue(value=category)))
    if max_price is not None:
        conditions.append(models.FieldCondition(key="price", range=models.Range(lte=max_price)))
    vector = GeminiEmbedder(gemini, settings.gemini).embed_query(query)
    hits = _qdrant(settings).search(
        vector, limit=limit, query_filter=models.Filter(must=conditions) if conditions else None
    )
    for hit in hits:
        payload = hit.payload
        console.print(
            f"[bold]{hit.score:.3f}[/] {hit.product_id} {payload.get('title')} "
            f"[dim]({payload.get('category')}, {payload.get('price')} {payload.get('currency')}, "
            f"ecosystems={payload.get('ecosystems')})[/]"
        )


def status() -> None:
    """Show catalog counts in PostgreSQL and Qdrant."""
    configure_logging()
    settings = get_settings()
    with _postgres(settings) as postgres:
        info = postgres.status()
    client = create_client(settings.qdrant)
    collection = settings.qdrant.collection
    points = client.count(collection, exact=True).count if client.collection_exists(collection) else 0
    print_counts("PostgreSQL products", info["products"])
    print_counts("Completeness", info["completeness"], humanize=False)
    print_counts("Web status", info["web_status"], humanize=False)
    print_counts("Compatibility facts by method", info["compatibility_facts_by_method"], humanize=False)
    print_counts("Qdrant", {"collection": collection, "points": points})
    if info["last_run"]:
        console.print_json(json.dumps(info["last_run"], default=str))
