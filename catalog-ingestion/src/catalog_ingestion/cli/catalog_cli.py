from typing import ClassVar

import typer

from catalog_ingestion.cli.analyze_command import AnalyzeCommand
from catalog_ingestion.cli.ingest_command import IngestCommand
from catalog_ingestion.cli.init_command import InitCommand
from catalog_ingestion.cli.reindex_command import ReindexCommand
from catalog_ingestion.cli.search_command import SearchCommand
from catalog_ingestion.cli.status_command import StatusCommand


class CatalogCli:
    """The `catalog-ingestion` command line: one command class per subcommand."""

    app: ClassVar[typer.Typer] = typer.Typer(
        name="catalog-ingestion",
        help="Catalog ingestion and enrichment for the HomePilot smart home agent.",
        no_args_is_help=True,
        add_completion=False,
    )
    app.command("init")(InitCommand.run)
    app.command("ingest")(IngestCommand.run)
    app.command("reindex")(ReindexCommand.run)
    app.command("analyze")(AnalyzeCommand.run)
    app.command("search")(SearchCommand.run)
    app.command("status")(StatusCommand.run)

    @staticmethod
    def main() -> None:
        CatalogCli.app()
