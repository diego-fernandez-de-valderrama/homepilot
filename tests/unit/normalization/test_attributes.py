from catalog_ingestion.normalization.attributes import parse_attributes, split_values
from tests.conftest import DANGLING_ATTRIBUTE, RICH_SCHELLENBERG, load_fixture_json


def test_parses_badges_sections_and_pairs():
    parsed = parse_attributes(load_fixture_json(RICH_SCHELLENBERG)["attributes"])
    assert parsed.badges == ("Nicht im Hausmüll entsorgen",)
    assert parsed.get("Unterstützte Sprachsteuerung") == "Amazon Alexa"
    assert parsed.get("Frequenz") == "868,4 MHz"
    assert parsed.get("EAN") == "4003971200178"
    entry = parsed.get_all("Nennspannung")[0]
    assert entry.section == "Technische Daten"
    assert parsed.unparsed_lines == ()


def test_sub_header_bestaendigkeit_does_not_shift_pairs():
    blob = "Technische Daten\nSmart Home-fähig\nJa\nBeständigkeit\nBetriebstemperatur\n0 - 50 °C"
    parsed = parse_attributes(blob)
    assert parsed.get("Betriebstemperatur") == "0 - 50 °C"
    assert parsed.get("Smart Home-fähig") == "Ja"


def test_dangling_line_is_kept_unparsed():
    parsed = parse_attributes(load_fixture_json(DANGLING_ATTRIBUTE)["attributes"])
    assert parsed.unparsed_lines == ("Witterungsbeständig",)
    assert parsed.get("Montage") == "Wandmontage"


def test_empty_blob():
    parsed = parse_attributes("")
    assert parsed.is_empty
    assert parsed.badges == ()


def test_repeated_section_is_supported():
    blob = "Weiterführende Produktinformationen\nHinweise\nA\nWeiterführende Produktinformationen\nEAN\n123"
    parsed = parse_attributes(blob)
    assert parsed.get("Hinweise") == "A"
    assert parsed.get("EAN") == "123"


def test_split_values_keeps_decimal_commas():
    assert split_values("Amazon Alexa, Google Assistant") == ("Amazon Alexa", "Google Assistant")
    assert split_values("5,7 W, RGBW") == ("5,7 W", "RGBW")


def test_split_values_keeps_commas_inside_parentheses():
    value = "Nanoleaf-App (Mobiltelefon, Tablet oder Desktop) oder Schalter (bis zu 30 intelligente Leuchten), Siri"
    assert split_values(value) == (
        "Nanoleaf-App (Mobiltelefon, Tablet oder Desktop) oder Schalter (bis zu 30 intelligente Leuchten)",
        "Siri",
    )
