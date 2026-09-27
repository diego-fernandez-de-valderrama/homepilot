from catalog_ingestion.models import AttributeEntry, ParsedAttributes


class AttributeParser:
    """Parser for the flattened `attributes` blob.

    Structure observed across the whole dataset:

        <badge lines>                     e.g. "Nicht im Hausmüll entsorgen", "Dimmbar", "RGBW"
        <section header>                  one of SECTION_HEADERS (a section may repeat)
        <key>\\n<value>\\n<key>\\n<value>   alternating lines
        Beständigkeit                     a sub-header without a value (dropped)

    A section with an odd number of lines leaves one dangling line; it is kept in
    `unparsed_lines` instead of shifting every following key/value pair.
    """

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

    @staticmethod
    def parse(blob: str) -> ParsedAttributes:
        lines = [line.strip() for line in blob.splitlines()]
        lines = [line for line in lines if line and line not in AttributeParser.SUB_HEADERS]

        badges: list[str] = []
        index = 0
        while index < len(lines) and lines[index] not in AttributeParser.SECTION_HEADERS:
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
            if line in AttributeParser.SECTION_HEADERS:
                flush()
                section, buffer = line, []
            else:
                buffer.append(line)
        flush()

        return ParsedAttributes(badges=tuple(badges), entries=tuple(entries), unparsed_lines=tuple(unparsed))

    @staticmethod
    def split_values(value: str) -> tuple[str, ...]:
        """Split a list-valued attribute ("Amazon Alexa, Google Assistant").

        Only `, ` (comma + space) separates items; decimal commas ("5,7 W") and commas inside
        parentheses ("Nanoleaf-App (Mobiltelefon, Tablet oder Desktop)") are kept.
        """
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        index = 0
        while index < len(value):
            char = value[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            if depth == 0 and value.startswith(", ", index):
                parts.append("".join(current))
                current = []
                index += 2
                continue
            current.append(char)
            index += 1
        parts.append("".join(current))
        return tuple(part.strip() for part in parts if part.strip())
