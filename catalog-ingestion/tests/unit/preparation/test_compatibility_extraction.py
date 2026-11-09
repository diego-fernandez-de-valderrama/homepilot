import dataclasses

from catalog_ingestion.models import AttributeEntry, ParsedAttributes
from catalog_ingestion.preparation import CompatibilityExtractor
from catalog_ingestion.vocabulary import Dimension, FactSource, FactStatus, Method
from tests.conftest import (
    AQARA_THREAD,
    BOSCH_CONTROLLER,
    HOMEMATIC_CCU2,
    HUE_BRIDGE,
    SHELLY_ZWAVE,
    SPARSE_MATTER,
    load_normalized,
)


def _supported(product_id: str, dimension: Dimension) -> set[str | None]:
    facts = CompatibilityExtractor.extract(load_normalized(product_id))
    return {f.canonical_value for f in facts if f.dimension is dimension and f.status is FactStatus.SUPPORTED}


def test_attribute_facts_carry_catalog_evidence():
    facts = CompatibilityExtractor.extract(load_normalized(BOSCH_CONTROLLER))
    alexa = next(f for f in facts if f.canonical_value == "amazon_alexa")
    assert alexa.evidence.source is FactSource.CATALOG
    assert alexa.evidence.text == "Unterstützte Sprachsteuerung: Google Assistant, Amazon Alexa, Apple Siri"
    assert alexa.evidence.field == "attributes.Unterstützte Sprachsteuerung"
    assert alexa.method is Method.DETERMINISTIC
    assert alexa.confidence == 1.0


def test_siri_does_not_imply_homekit():
    assert "apple_siri" in _supported(HOMEMATIC_CCU2, Dimension.VOICE_ASSISTANT)
    assert "apple_home" not in _supported(HOMEMATIC_CCU2, Dimension.ECOSYSTEM)


def test_compound_smart_control_values_are_split():
    ecosystems = _supported(HUE_BRIDGE, Dimension.ECOSYSTEM)
    assert {"philips_hue", "google_home"} <= ecosystems
    assert "google_assistant" not in ecosystems


def test_aqara_thread_and_multi_ecosystem():
    assert _supported(AQARA_THREAD, Dimension.PROTOCOL) == {"thread"}
    assert {"apple_home", "google_home", "samsung_smartthings", "aqara_home"} <= _supported(
        AQARA_THREAD, Dimension.ECOSYSTEM
    )
    assert "amazon_alexa" in _supported(AQARA_THREAD, Dimension.VOICE_ASSISTANT)


def test_matter_from_title_is_not_wifi():
    facts = CompatibilityExtractor.extract(load_normalized(SPARSE_MATTER))
    assert [(f.dimension, f.canonical_value, f.evidence.field) for f in facts] == [
        (Dimension.ECOSYSTEM, "matter", "title")
    ]


def test_unmapped_values_are_kept_raw():
    facts = CompatibilityExtractor.extract(load_normalized(SHELLY_ZWAVE))
    raw_only = [f for f in facts if f.canonical_value is None]
    assert any(f.raw_value == "Smart Hub" and f.dimension is Dimension.CONTROL for f in raw_only)
    assert "z_wave" in _supported(SHELLY_ZWAVE, Dimension.PROTOCOL)


def test_no_unsupported_facts_from_absence():
    for product_id in (SPARSE_MATTER, HUE_BRIDGE, BOSCH_CONTROLLER):
        facts = CompatibilityExtractor.extract(load_normalized(product_id))
        assert all(f.status is FactStatus.SUPPORTED for f in facts)


def test_voice_assistants_named_inside_a_control_value_become_facts():
    product = load_normalized(SPARSE_MATTER)
    value = "Per Smartphone oder über Sprachsteuerung wie Google Assistant & Amazon Alexa"
    attributes = ParsedAttributes(
        badges=(), entries=(AttributeEntry("Technik", "Smarte Steuerung", value),), unparsed_lines=()
    )
    facts = CompatibilityExtractor.extract(dataclasses.replace(product, attributes=attributes))
    voice = {f.canonical_value: f for f in facts if f.dimension is Dimension.VOICE_ASSISTANT}
    assert set(voice) == {"google_assistant", "amazon_alexa"}
    assert voice["amazon_alexa"].raw_value == "Amazon Alexa"
    assert voice["amazon_alexa"].evidence.text == f"Smarte Steuerung: {value}"
    assert "google_home" not in {f.canonical_value for f in facts}  # the assistant is not the ecosystem
