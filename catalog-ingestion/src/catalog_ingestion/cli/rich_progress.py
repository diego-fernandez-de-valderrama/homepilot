from typing import ClassVar, Self

from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from catalog_ingestion.cli._console import CONSOLE


class RichProgress:
    """The pipeline's `ProgressSink` as rich progress bars."""

    _STAGE_LABELS: ClassVar[dict[str, str]] = {
        "enrich": "Normalize / web / LLM / validate / PostgreSQL",
        "embed": "Embed + index in Qdrant",
    }

    def __init__(self) -> None:
        self._progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=CONSOLE,
        )
        self._tasks: dict[str, TaskID] = {}

    def __enter__(self) -> Self:
        self._progress.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._progress.stop()

    def start(self, stage: str, total: int) -> None:
        self._tasks[stage] = self._progress.add_task(self._STAGE_LABELS.get(stage, stage), total=total)

    def advance(self, stage: str, amount: int = 1) -> None:
        self._progress.advance(self._tasks[stage], amount)

    def finish(self, stage: str) -> None:
        task = self._tasks[stage]
        self._progress.update(task, completed=self._progress.tasks[task].total)
