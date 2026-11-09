from typing import Annotated

import typer
from qdrant_client import models

from catalog_ingestion.cli._console import CONSOLE
from catalog_ingestion.cli._resources import CliResources
from catalog_ingestion.core import AppSettings, LogSetup
from catalog_ingestion.indexing import GeminiEmbedder


class SearchCommand:
    @staticmethod
    def run(
        query: Annotated[str, typer.Argument(help="Natural language query (English or German).")],
        limit: Annotated[int, typer.Option(min=1, max=50)] = 5,
        ecosystem: Annotated[str | None, typer.Option(help="Filter: canonical ecosystem, e.g. apple_home.")] = None,
        category: Annotated[str | None, typer.Option(help="Filter: category key, e.g. heating_control.")] = None,
        max_price: Annotated[float | None, typer.Option(help="Filter: maximum price in EUR.")] = None,
    ) -> None:
        """Semantic search smoke test against Qdrant (with optional payload filters)."""
        LogSetup.configure()
        settings = AppSettings.current()
        gemini = CliResources.gemini(settings)
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
        hits = CliResources.qdrant(settings).search(
            vector, limit=limit, query_filter=models.Filter(must=conditions) if conditions else None
        )
        for hit in hits:
            payload = hit.payload
            CONSOLE.print(
                f"[bold]{hit.score:.3f}[/] {hit.product_id} {payload.get('title')} "
                f"[dim]({payload.get('category')}, {payload.get('price')} {payload.get('currency')}, "
                f"ecosystems={payload.get('ecosystems')})[/]"
            )
