import typer

from catalog_ingestion.cli import commands

app = typer.Typer(
    name="catalog-ingestion",
    help="Catalog ingestion and enrichment for the HomePilot smart home agent.",
    no_args_is_help=True,
    add_completion=False,
)
app.command()(commands.init)
app.command()(commands.ingest)
app.command()(commands.reindex)
app.command()(commands.analyze)
app.command()(commands.search)
app.command()(commands.status)


def main() -> None:
    app()
