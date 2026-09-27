from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Description:
    highlights: tuple[str, ...]
    text: str

    @property
    def is_empty(self) -> bool:
        return not self.highlights and not self.text
