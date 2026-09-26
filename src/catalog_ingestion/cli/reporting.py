"""Console output: progress bars and summary tables (rich)."""

from typing import Any, Self

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console(stderr=True)

_STAGE_LABELS = {"enrich": "Normalize / web / LLM / validate / PostgreSQL", "embed": "Embed + index in Qdrant"}


class RichProgress:
    def __init__(self) -> None:
        self._progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )
        self._tasks: dict[str, TaskID] = {}

    def __enter__(self) -> Self:
        self._progress.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._progress.stop()

    def start(self, stage: str, total: int) -> None:
        self._tasks[stage] = self._progress.add_task(_STAGE_LABELS.get(stage, stage), total=total)

    def advance(self, stage: str, amount: int = 1) -> None:
        self._progress.advance(self._tasks[stage], amount)

    def finish(self, stage: str) -> None:
        task = self._tasks[stage]
        self._progress.update(task, completed=self._progress.tasks[task].total)


def _label(name: str) -> str:
    return name.replace("_", " ").capitalize()


def print_counts(title: str, counts: dict[str, Any], humanize: bool = True) -> None:
    table = Table(title=title, show_header=False, title_justify="left")
    table.add_column("metric")
    table.add_column("value", justify="right")
    for name, value in counts.items():
        table.add_row(_label(name) if humanize else name, f"{value:,}" if isinstance(value, int) else str(value))
    console.print(table)
