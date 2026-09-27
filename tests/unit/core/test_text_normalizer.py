from catalog_ingestion.core import TextNormalizer


def test_typographic_punctuation_and_spaces_are_folded_to_ascii():
    text = "„Kein Hub“ – it’s ‚ok‘ — Zigbee Gateway´s"
    assert TextNormalizer.fold(text) == "\"Kein Hub\" - it's 'ok' - Zigbee Gateway's"


def test_letters_and_symbols_are_kept():
    assert TextNormalizer.fold("Weiß, Türkontakt, 24,95 €, 5 °C, 2 × AA") == "Weiß, Türkontakt, 24,95 €, 5 °C, 2 × AA"


def test_normalize_collapses_whitespace_and_casefolds():
    assert TextNormalizer.normalize("  Matter  KOMPATIBEL\n  mit HomeKit ") == "matter kompatibel mit homekit"
    assert TextNormalizer.normalize("Weiß") == "weiss"


def test_normalize_lines_keeps_line_breaks():
    assert TextNormalizer.normalize_lines("Funk:  Zigbee\n\n  Hub – nötig ") == "funk: zigbee\nhub - nötig"
