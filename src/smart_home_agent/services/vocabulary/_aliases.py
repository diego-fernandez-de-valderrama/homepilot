"""Conversational aliases on top of the ingestion vocabulary. Values are always existing canonical ids."""

import re

from catalog_ingestion.vocabulary import compatibility as compatibility_vocabulary

# Conversational forms that are not in the ingestion alias list. Values are existing canonical ids.
EXTRA_TERM_ALIASES: dict[str, str] = {
    "apple homekit": "apple_home",
    "home kit": "apple_home",
    "google home app": "google_home",
    "nest": "google_nest",
    "echo": "amazon_alexa",
    "hey google": "google_assistant",
    "ok google": "google_assistant",
    "smart things": "samsung_smartthings",
    "bosch": "bosch_smart_home",
    "homematic": "homematic_ip",
    "hue": "philips_hue",
    "z wave": "z_wave",
    "ble": "bluetooth",
    "wireless lan": "wifi",
}
AMBIGUOUS_TERMS: dict[str, tuple[str, ...]] = {
    "apple": ("apple_home", "apple_siri"),
    "google": ("google_home", "google_assistant", "google_nest"),
    "amazon": ("amazon_alexa",),  # only one Amazon concept exists; resolved directly by `resolve_term`
}
TERM_SUFFIXES = re.compile(r"[\s-]*(compatible|compatibility|kompatibel|kompatibilität|support|unterstützung)$")

# Everyday words for the canonical categories (EN and DE, singular; a trailing plural "s"/"e"/"en" is stripped).
CATEGORY_SYNONYMS: dict[str, str] = {
    "thermostat": "heating_control",
    "smart thermostat": "heating_control",
    "radiator thermostat": "heating_control",
    "heizkörperthermostat": "heating_control",
    "thermostatkopf": "heating_control",
    "heating": "heating_control",
    "heizung": "heating_control",
    "motion sensor": "motion_sensor",
    "motion detector": "motion_sensor",
    "präsenzmelder": "motion_sensor",
    "bulb": "smart_bulb",
    "light bulb": "smart_bulb",
    "smart bulb": "smart_bulb",
    "glühbirne": "smart_bulb",
    "plug": "smart_plug",
    "smart plug": "smart_plug",
    "steckdose": "smart_plug",
    "zwischenstecker": "smart_plug",
    "camera": "security_camera",
    "kamera": "security_camera",
    "doorbell": "doorbell_intercom",
    "türklingel": "doorbell_intercom",
    "klingel": "doorbell_intercom",
    "lock": "door_lock",
    "smart lock": "door_lock",
    "türschloss": "door_lock",
    "smoke detector": "safety_detector",
    "rauchmelder": "safety_detector",
    "water detector": "safety_detector",
    "door sensor": "contact_sensor",
    "window sensor": "contact_sensor",
    "fensterkontakt": "contact_sensor",
    "türkontakt": "contact_sensor",
    "hub": "hub_gateway",
    "gateway": "hub_gateway",
    "bridge": "hub_gateway",
    "zentrale": "hub_gateway",
    "smart speaker": "smart_speaker_display",
    "smart display": "smart_speaker_display",
    "switch": "switch",
    "dimmer": "switch",
    "schalter": "switch",
    "led strip": "led_strip",
    "light strip": "led_strip",
    "blind": "shutter_blind_control",
    "shutter": "shutter_blind_control",
    "rollladen": "shutter_blind_control",
    "robot mower": "robot_mower",
    "alarm": "alarm_system",
    "remote": "remote_control",
    "air conditioner": "climate_appliance",
    "wallbox": "ev_charging",
}
AMBIGUOUS_CATEGORIES: dict[str, tuple[str, ...]] = {
    "sensor": ("motion_sensor", "contact_sensor", "climate_sensor", "safety_detector"),
    "light": ("smart_bulb", "ceiling_light", "lamp", "outdoor_light", "led_strip", "led_panel"),
    "licht": ("smart_bulb", "ceiling_light", "lamp", "outdoor_light", "led_strip", "led_panel"),
    "leuchte": ("ceiling_light", "lamp", "outdoor_light"),
    "lampe": ("smart_bulb", "lamp"),  # German "Lampe" is both a bulb and a lamp
}

# Concepts that users often confuse. Used only for explanatory notes; they never change a status.
RELATED_NOT_EQUIVALENT: dict[str, tuple[str, ...]] = {
    "google_home": ("google_assistant", "google_nest"),
    "google_assistant": ("google_home",),
    "google_nest": ("google_home",),
    "apple_home": ("apple_siri",),
    "apple_siri": ("apple_home",),
    "matter": ("thread",),
    "thread": ("matter",),
    "wifi": ("proprietary_rf",),
    "zigbee": ("matter",),
}


def key(value: str) -> str:
    return compatibility_vocabulary.normalize_alias(value)


def singulars(value: str) -> list[str]:
    """The value and its possible singulars. "n" is tried before "en", so "Lampen"/"Leuchten" reach "Lampe"/
    "Leuchte" (like their singular) before "lamp"/"leucht"."""
    forms = [value]
    for suffix in ("n", "en", "es", "s", "e"):
        if value.endswith(suffix) and len(value) > len(suffix) + 3:
            forms.append(value[: -len(suffix)])
    return forms
