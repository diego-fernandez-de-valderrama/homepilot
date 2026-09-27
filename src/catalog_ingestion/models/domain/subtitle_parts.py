from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubtitleParts:
    features: tuple[str, ...]
    properties: tuple[tuple[str, str], ...]
