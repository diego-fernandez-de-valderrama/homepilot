import pytest

from catalog_ingestion.normalization.brand import detect_brand
from catalog_ingestion.normalization.text import parse_description, parse_subtitle
from tests.conftest import HUE_BRIDGE, load_fixture_json


def test_subtitle_features_and_properties():
    parts = parse_subtitle("Weiß, Batteriebetrieben, 23 x 22 x 75 mm, Farbe Gehäuse: Silber, 5,7 W")
    assert parts.features == ("Weiß", "Batteriebetrieben", "23 x 22 x 75 mm", "5,7 W")
    assert parts.properties == (("Farbe Gehäuse", "Silber"),)


def test_description_highlights_and_body():
    description = parse_description(load_fixture_json(HUE_BRIDGE)["description"])
    assert description.highlights[0] == "Steuerung von bis zu 50 passenden Artikeln gleichzeitig"
    assert "Basierend auf ZigBee-Technologie" in description.highlights
    assert description.text.startswith("Die Philips Hue Steuerzentrale Bridge")


def test_empty_description():
    assert parse_description("").is_empty


@pytest.mark.parametrize(
    ("title", "brand"),
    [
        ("Philips Hue Steuerzentrale Bridge", "Philips Hue"),
        ("Philips Wiz Smart-LED-Lampe", "Philips"),
        ("Homematic IP Funk-Fensterkontakt HmIP-SWDM-2", "Homematic IP"),
        ("Bosch Smart Home Funk-Fensterkontakt II [+M] Matter", "Bosch"),
        ("Burg-Wächter Türschloss", "Burg-Wächter"),
        ("Überwachungskamera HB8 2K+", None),
        ("Ringlicht ohne Marke", None),
    ],
)
def test_detect_brand(title, brand):
    assert detect_brand(title) == brand
