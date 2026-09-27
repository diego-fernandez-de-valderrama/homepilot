import pytest
from catalog_ingestion.domain.enums import Dimension
from catalog_ingestion.vocabulary import compatibility as compatibility_vocabulary

from smart_home_agent.services import vocabulary
from smart_home_agent.services.vocabulary import TermResolutionError


@pytest.mark.parametrize(
    ("value", "canonical", "dimension"),
    [
        ("HomeKit", "apple_home", Dimension.ECOSYSTEM),
        ("Apple HomeKit", "apple_home", Dimension.ECOSYSTEM),
        ("Siri", "apple_siri", Dimension.VOICE_ASSISTANT),
        ("Google Home", "google_home", Dimension.ECOSYSTEM),
        ("Google Assistant", "google_assistant", Dimension.VOICE_ASSISTANT),
        ("Alexa", "amazon_alexa", Dimension.VOICE_ASSISTANT),
        ("Matter", "matter", Dimension.ECOSYSTEM),
        ("matter-kompatibel", "matter", Dimension.ECOSYSTEM),
        ("Zigbee", "zigbee", Dimension.PROTOCOL),
        ("Z-Wave", "z_wave", Dimension.PROTOCOL),
        ("WLAN", "wifi", Dimension.PROTOCOL),
        ("Bluetooth", "bluetooth", Dimension.PROTOCOL),
        ("Samsung SmartThings", "samsung_smartthings", Dimension.ECOSYSTEM),
        ("Bosch Smart Home", "bosch_smart_home", Dimension.ECOSYSTEM),
        ("Homematic IP", "homematic_ip", Dimension.ECOSYSTEM),
        ("google_home", "google_home", Dimension.ECOSYSTEM),
    ],
)
def test_terms_resolve_to_existing_canonical_ids(value, canonical, dimension):
    resolved = vocabulary.resolve_term(value)
    assert (resolved.canonical, resolved.dimension) == (canonical, dimension)


def test_every_label_resolves_back_to_its_term():
    # Tool results name terms by label; the model passes them back verbatim ("Apple Home (HomeKit)").
    for known in compatibility_vocabulary.TERMS:
        assert vocabulary.resolve_term(known.label).canonical == known.canonical


def test_no_alias_crosses_concepts():
    assert vocabulary.resolve_term("Siri").canonical != vocabulary.resolve_term("HomeKit").canonical
    assert vocabulary.resolve_term("Google Assistant").canonical != vocabulary.resolve_term("Google Home").canonical
    assert vocabulary.resolve_term("Matter").dimension is not Dimension.PROTOCOL
    assert vocabulary.resolve_term("Zigbee").canonical != "matter"


@pytest.mark.parametrize("value", ["Apple", "Google"])
def test_ambiguous_terms_ask_instead_of_guessing(value):
    with pytest.raises(TermResolutionError) as info:
        vocabulary.resolve_term(value)
    assert len(info.value.options) >= 2


def test_unknown_term_is_rejected():
    with pytest.raises(TermResolutionError) as info:
        vocabulary.resolve_term("Teletubby Protocol")
    assert info.value.options == []


def test_resolve_terms_deduplicates():
    assert [t.canonical for t in vocabulary.resolve_terms(["HomeKit", "Apple Home", ""])] == ["apple_home"]


@pytest.mark.parametrize(
    ("value", "key"),
    [
        ("heating_control", "heating_control"),
        ("Thermostat", "heating_control"),
        ("thermostats", "heating_control"),
        ("Heizkörperthermostat", "heating_control"),
        ("Motion sensor", "motion_sensor"),
        ("Bewegungsmelder", "motion_sensor"),
        ("smart plug", "smart_plug"),
        ("Überwachungskamera", "security_camera"),
    ],
)
def test_categories(value, key):
    assert vocabulary.resolve_category(value) == key


def test_ambiguous_category():
    with pytest.raises(TermResolutionError) as info:
        vocabulary.resolve_category("sensor")
    assert "motion_sensor" in info.value.options


def test_owned_devices():
    assert vocabulary.resolve_owned_device("Hue Bridge") == "philips_hue_bridge"
    assert vocabulary.resolve_owned_device("Homematic IP Access Point") == "homematic_ip_access_point"
    with pytest.raises(TermResolutionError):
        vocabulary.resolve_owned_device("some gateway")  # generic hub says nothing about compatibility
    assert vocabulary.resolve_owned_device("Hue-Bridge") == "philips_hue_bridge"  # German spelling


def test_is_hub_only_for_specific_hubs():
    assert vocabulary.is_hub("philips_hue_bridge") and vocabulary.is_hub("gardena_smart_gateway")
    assert not any(vocabulary.is_hub(c) for c in ("smart_hub", "smartphone", "wifi_network", "ring_subscription"))


def test_vocabulary_overview_lists_canonical_ids():
    text = vocabulary.vocabulary_overview()
    for canonical in (
        "apple_home",
        "apple_siri",
        "google_home",
        "google_assistant",
        "matter",
        "zigbee",
        "heating_control",
    ):
        assert canonical in text


@pytest.mark.parametrize(
    "value",
    [
        "Fritz!Box Access Point",
        "Ubiquiti UniFi access point",
        "WLAN Access Point",
        "Aqara smart home controller",
        "Homey Pro Smart Home Controller",
        "smart_hub",
        "standalone",
        "Stand-alone",
        "third_party_partner_solution",
    ],
)
def test_owned_devices_never_guess_a_specific_hub(value):
    with pytest.raises(TermResolutionError):
        vocabulary.resolve_owned_device(value)


def test_owned_devices_with_the_brand_still_resolve():
    assert vocabulary.resolve_owned_device("Homematic Access Point") == "homematic_ip_access_point"
    assert vocabulary.resolve_owned_device("HmIP Access Point") == "homematic_ip_access_point"
    assert vocabulary.resolve_owned_device("Bosch Smart Home Controller II") == "bosch_smart_home_controller"
    assert vocabulary.resolve_owned_device("CCU3") == "homematic_ccu3"
    assert vocabulary.resolve_owned_device("smartphone") == "smartphone"  # a non-hub device the customer owns


def test_vocabulary_overview_does_not_offer_the_generic_hub():
    hubs_line = next(line for line in vocabulary.vocabulary_overview().splitlines() if line.startswith("Hubs"))
    assert "smart_hub" not in hubs_line and "philips_hue_bridge" in hubs_line


@pytest.mark.parametrize("word", ["Lampe", "Lampen"])
def test_lampe_is_ambiguous_in_singular_and_plural(word):
    with pytest.raises(TermResolutionError) as error:
        vocabulary.resolve_category(word)
    assert set(error.value.options) == {"smart_bulb", "lamp"}


def test_leuchten_resolves_like_leuchte():
    with pytest.raises(TermResolutionError) as error:
        vocabulary.resolve_category("Leuchten")
    assert "lamp" in error.value.options
