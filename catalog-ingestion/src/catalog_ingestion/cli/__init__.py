"""The `catalog-ingestion` command line (the top layer: builds the components and injects them).

`CatalogCli.main` runs the Typer app; each subcommand is one class with a `run` method:
`InitCommand` (migrations + Qdrant collection), `IngestCommand`, `ReindexCommand`, `AnalyzeCommand`
(dataset profile), `SearchCommand` (semantic search smoke test), `StatusCommand`. Private `_resources`
builds the Gemini client, repositories and input path; `RichProgress` and `_counts_printer` render output.
"""

from catalog_ingestion.cli.catalog_cli import CatalogCli

__all__ = ["CatalogCli"]
