import re

from catalog_ingestion.core import TextNormalizer
from catalog_ingestion.enrichment.validation._source_texts import SourceTexts
from catalog_ingestion.models import Spec


class SpecCheck:
    """A spec is kept when its value appears in a source, or when each of its numbers appears there as a
    whole number (followed by the spec's unit, when it has one)."""

    _NUMBER = re.compile(r"\d+(?:[.,]\d+)*")

    @staticmethod
    def supported(spec: Spec, sources: SourceTexts) -> bool:
        combined = f"{sources.catalog}\n{sources.web}"
        value = TextNormalizer.normalize(spec.value)
        if value and re.search(rf"(?<![\w.,]){re.escape(value)}(?![\w]|[.,]\d)", combined):
            return True
        numbers = SpecCheck._NUMBER.findall(spec.value)
        return bool(numbers) and all(
            SpecCheck._number_pattern(number, spec.unit).search(combined) for number in numbers
        )

    @staticmethod
    def _number_pattern(number: str, unit: str | None) -> re.Pattern[str]:
        # Whole numbers only ("4" is not found in "2,4 GHz"); a unit must follow the number.
        unit_part = rf"\s*{re.escape(TextNormalizer.normalize(unit))}(?!\w)" if unit and unit.strip() else ""
        return re.compile(rf"(?<![\d.,]){re.escape(number)}(?![\d]|[.,]\d){unit_part}")
