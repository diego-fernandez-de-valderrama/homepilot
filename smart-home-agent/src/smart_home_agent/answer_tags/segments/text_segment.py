from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextSegment:
    text: str  # markdown, may contain inline <item/> tags
