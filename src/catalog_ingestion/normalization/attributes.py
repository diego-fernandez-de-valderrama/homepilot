"""Parser for the flattened `attributes` blob.

Structure observed across the whole dataset:

    <badge lines>                     e.g. "Nicht im Hausmüll entsorgen", "Dimmbar", "RGBW"
    <section header>                  one of SECTION_HEADERS (a section may repeat)
    <key>\\n<value>\\n<key>\\n<value>   alternating lines
    Beständigkeit                     a sub-header without a value (dropped)

A section with an odd number of lines leaves one dangling line; it is kept in
`unparsed_lines` instead of shifting every following key/value pair.
"""

from catalog_ingestion.domain.product import AttributeEntry, ParsedAttributes

SECTION_HEADERS: frozenset[str] = frozenset(
    {
        "Farbe, Optik & Gestalt",
        "Maße, Volumen- & Gewichtsangaben",
        "Ausstattungsmerkmale & Funktionen",
        "Technische Daten",
        "Anwendungs-, Montage- & Verarbeitungshinweise",
        "Rechtliche Hinweise & Normen",
        "Weiterführende Produktinformationen",
        "Material- & Oberflächeneigenschaften",
    }
)
SUB_HEADERS: frozenset[str] = frozenset({"Beständigkeit"})


def parse_attributes(blob: str) -> ParsedAttributes:
    lines = [line.strip() for line in blob.splitlines()]
    lines = [line for line in lines if line and line not in SUB_HEADERS]

    badges: list[str] = []
    index = 0
    while index < len(lines) and lines[index] not in SECTION_HEADERS:
        badges.append(lines[index])
        index += 1

    entries: list[AttributeEntry] = []
    unparsed: list[str] = []
    section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if section is None:
            return
        pairs = len(buffer) // 2
        for position in range(pairs):
            entries.append(AttributeEntry(section, buffer[2 * position], buffer[2 * position + 1]))
        if len(buffer) % 2:
            unparsed.append(buffer[-1])

    for line in lines[index:]:
        if line in SECTION_HEADERS:
            flush()
            section, buffer = line, []
        else:
            buffer.append(line)
    flush()

    return ParsedAttributes(badges=tuple(badges), entries=tuple(entries), unparsed_lines=tuple(unparsed))


def split_values(value: str) -> tuple[str, ...]:
    """Split a list-valued attribute ("Amazon Alexa, Google Assistant").

    Only `, ` (comma + space) separates items; decimal commas ("5,7 W") are kept.
    """
    return tuple(part.strip() for part in value.split(", ") if part.strip())
