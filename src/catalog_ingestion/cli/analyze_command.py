from dataclasses import asdict

from catalog_ingestion.cli._counts_printer import CountsPrinter
from catalog_ingestion.cli._resources import CliResources, InputOption
from catalog_ingestion.core import AppSettings, LogSetup
from catalog_ingestion.preparation import DatasetProfiler


class AnalyzeCommand:
    @staticmethod
    def run(input_path: InputOption = None) -> None:
        """Profile the dataset (no database needed)."""
        LogSetup.configure()
        settings = AppSettings.current()
        profile = DatasetProfiler.profile(CliResources.resolve_input(input_path, settings))
        for name, counts in asdict(profile).items():
            humanize = name in ("counts", "completeness_levels")
            CountsPrinter.print(CountsPrinter.label(name), counts, humanize=humanize)
