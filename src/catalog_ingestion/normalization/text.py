"""Subtitle and description parsing."""

from catalog_ingestion.domain.product import Description, SubtitleParts

DESCRIPTION_HEADER = "Produkt Highlights"
# Highlight bullets are short lines; the first long line starts the prose body.
_MAX_HIGHLIGHT_LENGTH = 150


def parse_subtitle(subtitle: str) -> SubtitleParts:
    """`Weiß, Batteriebetrieben, Farbe Gehäuse: Silber` -> features + key/value properties."""
    features: list[str] = []
    properties: list[tuple[str, str]] = []
    for token in (part.strip() for part in subtitle.split(", ")):
        if not token:
            continue
        key, separator, value = token.partition(": ")
        if separator and key and value:
            properties.append((key.strip(), value.strip()))
        else:
            features.append(token)
    return SubtitleParts(features=tuple(features), properties=tuple(properties))


def parse_description(description: str) -> Description:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    if not lines:
        return Description(highlights=(), text="")
    if lines[0] != DESCRIPTION_HEADER:
        return Description(highlights=(), text="\n".join(lines))
    highlights: list[str] = []
    index = 1
    while index < len(lines) and len(lines[index]) < _MAX_HIGHLIGHT_LENGTH:
        highlights.append(lines[index])
        index += 1
    return Description(highlights=tuple(highlights), text="\n".join(lines[index:]))
