from typing import Any

from rich.table import Table

from catalog_ingestion.cli._console import CONSOLE


class CountsPrinter:
    """Summary tables (metric -> value)."""

    @staticmethod
    def print(title: str, counts: dict[str, Any], humanize: bool = True) -> None:
        table = Table(title=title, show_header=False, title_justify="left")
        table.add_column("metric")
        table.add_column("value", justify="right")
        for name, value in counts.items():
            label = CountsPrinter.label(name) if humanize else name
            table.add_row(label, f"{value:,}" if isinstance(value, int) else str(value))
        CONSOLE.print(table)

    @staticmethod
    def label(name: str) -> str:
        return name.replace("_", " ").capitalize()
