"""Deterministic output checks (no model, in-memory catalog)."""

from collections.abc import Sequence

import pytest
from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.guardrail.categories import Category
from smart_home_agent.guardrail.classifier import GuardrailThresholds, SemanticGuardrail
from smart_home_agent.guardrail.output_check import OutputValidator
from tests.fakes import FakeCatalog, fact, product

THERMOSTAT = product(
    "30173510",
    title="Acme Smart Radiator Thermostat",
    facts=[fact("google_home"), fact("amazon_alexa"), fact("apple_home", FactStatus.UNKNOWN)],
)
PLUG = product(
    "30387250",
    title="Acme Zigbee Smart Plug",
    category="smart_plug",
    facts=[fact("zigbee"), fact("apple_home", FactStatus.UNSUPPORTED)],
)
TOOL_RESULTS = [{"status": "ok", "product": THERMOSTAT.model_dump(mode="json")}]


def validator(**kwargs) -> OutputValidator:
    return OutputValidator(FakeCatalog([THERMOSTAT, PLUG]), **kwargs)


def kinds(text: str, tool_results: Sequence[dict] = TOOL_RESULTS, **kwargs) -> list[str]:
    return [v.kind for v in validator(**kwargs).validate(text, tool_results)]


@pytest.mark.parametrize(
    "text",
    [
        "Switch off the breaker, then connect the brown wire to terminal L.",
        "Connect the neutral wire to the N terminal of the actuator.",
        "1. Strip the brown cable. 2. Screw the blue wire into the junction box.",
        "Schließen Sie den Neutralleiter an Klemme N an.",
        "Verbinde die Phase mit der Klemme L des Aktors.",
        "Zuerst die Sicherung ausschalten und dann die Ader an Klemme L anklemmen.",
    ],
)
def test_wiring_instructions_are_rejected(text):
    assert "electrical" in kinds(text)


@pytest.mark.parametrize(
    "text",
    [
        "This switch requires a neutral wire, so please check your wall box first.",
        "Installation requires a qualified electrician: I can't explain how to connect the live wire.",
        "Der Aktor benötigt einen Neutralleiter, der Anschluss muss von einer Elektrofachkraft erfolgen.",
        "Connect the hub to your router with the included cable, then pair the thermostat in the app.",
        "The Acme Smart Radiator Thermostat runs on batteries and needs no mains connection.",
    ],
)
def test_specifications_and_refusals_pass(text):
    assert kinds(text) == []


def test_unknown_product_id_is_rejected():
    assert kinds("I recommend 99999999 for your hallway.") == ["unknown_product"]


def test_product_ids_from_tools_or_catalog_pass():
    assert kinds("I recommend 30173510.") == []
    assert kinds("Also consider 30387250.") == []  # not in this turn's tools, but in the catalog


def test_product_ids_inside_answer_tags_are_checked():
    assert kinds('<items ids="30173510,99999999"/>') == ["unknown_product"]
    assert kinds('The <item id="30173510"/> fits.\n<compatibility id="30387250"/>') == []


def test_prices_and_eans_are_not_product_ids():
    assert kinds("It costs 49.99 EUR (EAN 4001234567890).") == []


def test_supported_compatibility_claim_passes():
    assert kinds("The Acme Smart Radiator Thermostat works with Google Home and Alexa.") == []
    assert kinds("30173510 ist kompatibel mit Amazon Alexa.") == []


def test_unknown_compatibility_claimed_as_supported_is_rejected():
    assert kinds("The Acme Smart Radiator Thermostat works with Apple HomeKit.") == ["unsupported_compatibility"]


def test_explicitly_unsupported_claim_is_rejected():
    tools = [{"status": "ok", "product": PLUG.model_dump(mode="json")}]
    assert kinds("The Acme Zigbee Smart Plug is compatible with HomeKit.", tools) == ["unsupported_compatibility"]


def test_hedged_or_negative_claims_pass():
    assert kinds("I can't confirm that the Acme Smart Radiator Thermostat works with HomeKit.") == []
    assert kinds("The Acme Smart Radiator Thermostat does not work with HomeKit.") == []


def test_claims_without_a_linked_product_pass():
    assert kinds("Many thermostats work with Apple HomeKit.") == []


def test_siri_claim_is_not_satisfied_by_homekit():
    tools = [
        {
            "status": "ok",
            "product": product("x1", title="Siri Speaker Plus", facts=[fact("apple_home")]).model_dump(mode="json"),
        }
    ]
    catalog = FakeCatalog([product("x1", title="Siri Speaker Plus", facts=[fact("apple_home")])])
    violations = OutputValidator(catalog).validate("The Siri Speaker Plus works with Apple Siri.", tools)
    assert [v.kind for v in violations] == ["unsupported_compatibility"]


def test_prompt_leak_is_rejected():
    assert kinds("I will call recommend_products now.", leak_markers=["recommend_products"]) == ["prompt_leak"]


def test_catalog_failure_skips_product_checks():
    class BrokenCatalog(FakeCatalog):
        def get_products(self, product_ids):
            raise ConnectionError("database down")

    assert OutputValidator(BrokenCatalog([])).validate("I recommend 99999999.", TOOL_RESULTS) == []


class FixedGuardrail(SemanticGuardrail):
    def __init__(self, category: Category) -> None:
        axes = {c: [[1.0 if i == n else 0.0 for i in range(4)]] for n, c in enumerate(list(Category)[:4])}
        thresholds = GuardrailThresholds(
            smart_home=0.5, electrical=0.5, off_topic=0.5, prompt_injection=0.5, margin=0.1
        )
        super().__init__(lambda texts: [axes[category][0] for _ in texts], axes, thresholds)


LONG_ANSWER = "Here is a classic carbonara: " + "boil the pasta, fry the guanciale, mix eggs and cheese. " * 5


def test_off_topic_answer_without_tools_is_rejected():
    assert kinds(LONG_ANSWER, [], guardrail=FixedGuardrail(Category.OFF_TOPIC)) == ["off_topic"]


def test_domain_check_skipped_for_tool_backed_or_short_answers():
    off_topic = FixedGuardrail(Category.OFF_TOPIC)
    assert kinds(LONG_ANSWER, TOOL_RESULTS, guardrail=off_topic) == []
    assert kinds("Hello! How can I help?", [], guardrail=off_topic) == []
    assert kinds(LONG_ANSWER, [], guardrail=FixedGuardrail(Category.SMART_HOME)) == []


def test_claim_about_a_product_from_the_session_is_checked_without_tools():
    text = "Yes, the Acme Smart Radiator Thermostat works with Apple HomeKit."
    assert [v.kind for v in validator().validate(text, [], ["30173510"])] == ["unsupported_compatibility"]
    assert validator().validate("Yes, the Acme Smart Radiator Thermostat works with Alexa.", [], ["30173510"]) == []
