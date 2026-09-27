from contextlib import ExitStack
from typing import Annotated

import typer

from catalog_ingestion.cli._console import CONSOLE
from catalog_ingestion.cli._counts_printer import CountsPrinter
from catalog_ingestion.cli._resources import CliResources, InputOption
from catalog_ingestion.cli.rich_progress import RichProgress
from catalog_ingestion.core import AppSettings, GeminiClient, GeminiModelNotFoundError, LogSetup
from catalog_ingestion.enrichment import Fetcher, GeminiUrlContextFetcher, HttpxFetcher, LLMEnricher, WebRetriever
from catalog_ingestion.indexing import GeminiEmbedder
from catalog_ingestion.pipeline import EmbeddingModelMismatchError, IngestionPipeline, IngestOptions


class IngestCommand:
    @staticmethod
    def run(
        input_path: InputOption = None,
        force: Annotated[bool, typer.Option(help="Ignore all caches: re-run LLM enrichment and re-embed.")] = False,
        skip_web: Annotated[
            bool, typer.Option(help="Do not fetch product pages (cached pages are still used).")
        ] = False,
        skip_llm: Annotated[
            bool,
            typer.Option(help="No LLM calls: stored LLM output is kept (also with --force), new products get none."),
        ] = False,
        refresh_web: Annotated[bool, typer.Option(help="Re-fetch product pages even if cached.")] = False,
        only_product: Annotated[
            list[str] | None, typer.Option(help="Process only this product id (repeatable).")
        ] = None,
        limit: Annotated[int | None, typer.Option(min=1, help="Process only the first N products.")] = None,
        concurrency: Annotated[int | None, typer.Option(min=1, max=64, help="Parallel web/LLM workers.")] = None,
    ) -> None:
        """Ingest products.zip into PostgreSQL and Qdrant (idempotent, incremental)."""
        LogSetup.configure()
        settings = AppSettings.current()
        options = IngestOptions(
            input_path=CliResources.resolve_input(input_path, settings),
            force=force,
            skip_web=skip_web,
            skip_llm=skip_llm,
            refresh_web=refresh_web,
            only_products=tuple(only_product or ()),
            limit=limit,
            concurrency=concurrency or settings.ingest.concurrency,
        )
        gemini = CliResources.gemini(settings)
        if gemini is not None:
            try:
                gemini.check_models()
            except GeminiModelNotFoundError as exc:
                CONSOLE.print(f"[red]Configuration error:[/] {exc}")
                raise typer.Exit(code=2) from exc
        with ExitStack() as stack:
            postgres = stack.enter_context(CliResources.postgres(settings, migrate=True))
            progress = stack.enter_context(RichProgress())
            pipeline = IngestionPipeline(
                postgres=postgres,
                qdrant=CliResources.qdrant(settings),
                embedder=GeminiEmbedder(gemini, settings.gemini) if gemini else None,
                web=IngestCommand._web_retriever(stack, settings, gemini, skip_web),
                enricher=LLMEnricher(gemini, settings.gemini.temperature) if gemini and not skip_llm else None,
                model_name=settings.gemini.model,
                progress=progress,
                max_deactivate_ratio=settings.ingest.max_deactivate_ratio,
            )
            try:
                stats = pipeline.ingest(options)
            except EmbeddingModelMismatchError as exc:
                CONSOLE.print(f"[red]Index error:[/] {exc}")
                raise typer.Exit(code=2) from exc
            except KeyboardInterrupt:
                if gemini is not None:
                    gemini.cancel()  # wake worker threads waiting on rate limits so the process exits now
                CONSOLE.print(
                    "\n[yellow]Interrupted.[/] Every product finished before the interruption is saved. "
                    "Run `ingest` again to continue with the remaining ones."
                )
                raise typer.Exit(code=130) from None
        CountsPrinter.print("Ingestion summary", stats.as_dict())

    @staticmethod
    def _web_retriever(
        stack: ExitStack, settings: AppSettings, gemini: GeminiClient | None, skip_web: bool
    ) -> WebRetriever | None:
        """HTTP first, then Gemini url_context (when configured); None when fetching is off."""
        fetchers: list[Fetcher] = []
        if settings.web.enabled and not skip_web:
            http = HttpxFetcher(settings.web)
            stack.callback(http.close)
            fetchers.append(http)
            if gemini is not None:
                fetchers.append(GeminiUrlContextFetcher(gemini, settings.web))
        return WebRetriever(fetchers) if fetchers else None
