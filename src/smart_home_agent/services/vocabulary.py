"""Maps what the user (or Gemini) says to the canonical catalog vocabulary.

The canonical terms, categories and requirement items are the ones defined by
`catalog-ingestion`; this module only adds conversational aliases that point to existing
canonical ids. Aliases never cross concepts: Siri is not HomeKit, Google Assistant is not
Google Home, Matter is not a transport protocol. Ambiguous input raises instead of guessing.
"""

import re
from dataclasses import dataclass

from catalog_ingestion.domain.enums import Dimension
from catalog_ingestion.vocabulary import categories as category_vocabulary
from catalog_ingestion.vocabulary import compatibility as compatibility_vocabulary
from catalog_ingestion.vocabulary import requirements as requirement_vocabulary


class TermResolutionError(ValueError):
    """The value maps to no canonical term, or to several (then `options` lists them)."""

    def __init__(self, kind: str, value: str, options: list[str] | None = None) -> None:
        self.kind = kind
        self.value = value
        self.options = options or []
        reason = f"ambiguous, could mean: {', '.join(self.options)}" if self.options else "not recognized"
        super().__init__(f"{kind} {value!r} is {reason}")


@dataclass(frozen=True, slots=True)
class ResolvedTerm:
    canonical: str
    dimension: Dimension
    label: str


# Conversational forms that are not in the ingestion alias list. Values are existing canonical ids.
_EXTRA_TERM_ALIASES: dict[str, str] = {
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
_AMBIGUOUS_TERMS: dict[str, tuple[str, ...]] = {
    "apple": ("apple_home", "apple_siri"),
    "google": ("google_home", "google_assistant", "google_nest"),
    "amazon": ("amazon_alexa",),  # only one Amazon concept exists; resolved directly below
}
_TERM_SUFFIXES = re.compile(r"[\s-]*(compatible|compatibility|kompatibel|kompatibilität|support|unterstützung)$")

# Everyday words for the canonical categories (EN and DE, singular; a trailing plural "s"/"e"/"en" is stripped).
_CATEGORY_SYNONYMS: dict[str, str] = {
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
    "lampe": "smart_bulb",
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
_AMBIGUOUS_CATEGORIES: dict[str, tuple[str, ...]] = {
    "sensor": ("motion_sensor", "contact_sensor", "climate_sensor", "safety_detector"),
    "light": ("smart_bulb", "ceiling_light", "lamp", "outdoor_light", "led_strip", "led_panel"),
    "licht": ("smart_bulb", "ceiling_light", "lamp", "outdoor_light", "led_strip", "led_panel"),
    "leuchte": ("ceiling_light", "lamp", "outdoor_light"),
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


def _key(value: str) -> str:
    return compatibility_vocabulary.normalize_alias(value)


def _singular(value: str) -> list[str]:
    forms = [value]
    for suffix in ("en", "es", "s", "e"):
        if value.endswith(suffix) and len(value) > len(suffix) + 3:
            forms.append(value[: -len(suffix)])
    return forms


def term(canonical: str) -> ResolvedTerm:
    found = compatibility_vocabulary.term_by_canonical(canonical)
    if found is None:
        raise TermResolutionError("compatibility term", canonical)
    return ResolvedTerm(found.canonical, found.dimension, found.label)


def label(canonical: str) -> str:
    found = compatibility_vocabulary.term_by_canonical(canonical)
    return found.label if found else canonical


def resolve_term(value: str) -> ResolvedTerm:
    """Free text ("HomeKit", "Google Home", "matter-kompatibel", "zigbee") -> canonical term."""
    key = _TERM_SUFFIXES.sub("", _key(value)).strip()
    if compatibility_vocabulary.term_by_canonical(key):
        return term(key)
    if key in _EXTRA_TERM_ALIASES:
        return term(_EXTRA_TERM_ALIASES[key])
    options = _AMBIGUOUS_TERMS.get(key)
    if options and len(options) == 1:
        return term(options[0])
    if options:
        raise TermResolutionError("compatibility term", value, [label(o) for o in options])
    found = compatibility_vocabulary.lookup(key)
    if found is None:
        raise TermResolutionError("compatibility term", value)
    return ResolvedTerm(found.canonical, found.dimension, found.label)


def resolve_terms(values: list[str] | None) -> list[ResolvedTerm]:
    resolved = [resolve_term(v) for v in values or [] if v.strip()]
    return list({t.canonical: t for t in resolved}.values())


def resolve_category(value: str) -> str:
    """Category key, English/German label, URL slug or an everyday word -> canonical category key."""
    key = _key(value)
    for form in _singular(key):
        if category_vocabulary.category_by_key(form.replace(" ", "_")):
            return form.replace(" ", "_")
        for category in category_vocabulary.CATEGORIES:
            if form in (_key(category.label_en), _key(category.label_de)) or form in category.slugs:
                return category.key
        if form in _CATEGORY_SYNONYMS:
            return _CATEGORY_SYNONYMS[form]
        if form in _AMBIGUOUS_CATEGORIES:
            raise TermResolutionError("category", value, list(_AMBIGUOUS_CATEGORIES[form]))
    raise TermResolutionError("category", value, [])


def resolve_owned_device(value: str) -> str:
    """Hub/gateway the user owns ("Hue Bridge", "Homematic Access Point") -> canonical requirement id."""
    key = _key(value)
    if requirement_vocabulary.term_by_canonical(key):
        return key
    found = requirement_vocabulary.lookup(value)
    if found is None or found.canonical == "smart_hub":
        raise TermResolutionError("owned device", value)
    return found.canonical


def requirement_label(canonical: str) -> str:
    found = requirement_vocabulary.term_by_canonical(canonical)
    if found:
        return found.label
    return "Stand-alone operation (no hub)" if canonical == "standalone" else canonical


def vocabulary_overview() -> str:
    """Canonical vocabulary as plain text, for the system instruction."""
    lines = ["Compatibility terms (canonical id: label):"]
    for dimension in (Dimension.ECOSYSTEM, Dimension.VOICE_ASSISTANT, Dimension.PROTOCOL, Dimension.MOBILE_OS):
        items = ", ".join(
            f"{t.canonical}: {t.label}" for t in compatibility_vocabulary.TERMS if t.dimension is dimension
        )
        lines.append(f"- {dimension.value}: {items}")
    lines.append("Categories (key: English / German):")
    lines.extend(f"- {c.key}: {c.label_en} / {c.label_de}" for c in category_vocabulary.CATEGORIES)
    hubs = ", ".join(
        f"{t.canonical}: {t.label}" for t in requirement_vocabulary.TERMS if t.kind.value in ("hub", "gateway")
    )
    lines.append(f"Hubs and gateways a user may own: {hubs}")
    return "\n".join(lines)
