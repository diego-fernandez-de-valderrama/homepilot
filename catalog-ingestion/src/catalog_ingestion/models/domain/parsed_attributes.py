from dataclasses import dataclass

from catalog_ingestion.models.domain.attribute_entry import AttributeEntry


@dataclass(frozen=True, slots=True)
class ParsedAttributes:
    badges: tuple[str, ...]
    entries: tuple[AttributeEntry, ...]
    unparsed_lines: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def get(self, key: str) -> str | None:
        """First value for `key`, or None."""
        return next((entry.value for entry in self.entries if entry.key == key), None)

    def get_all(self, key: str) -> tuple[AttributeEntry, ...]:
        return tuple(entry for entry in self.entries if entry.key == key)
