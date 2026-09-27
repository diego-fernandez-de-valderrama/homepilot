"""Canonical compatibility vocabulary.

Aliases never cross concepts: "Apple Siri" is a voice assistant and does not imply
Apple Home (HomeKit); "Google Assistant" does not imply Google Home; Matter is an
interoperability standard (ecosystem dimension) and is not a transport protocol.
A raw value without a safe mapping keeps `canonical_value=None`.
"""

import re
from dataclasses import dataclass

from catalog_ingestion.domain.enums import Dimension


@dataclass(frozen=True, slots=True)
class CompatibilityTerm:
    canonical: str
    dimension: Dimension
    label: str
    aliases: tuple[str, ...]


TERMS: tuple[CompatibilityTerm, ...] = (
    # Ecosystems, platforms and interoperability standards
    CompatibilityTerm("matter", Dimension.ECOSYSTEM, "Matter", ("matter", "[+m] matter")),
    CompatibilityTerm(
        "apple_home",
        Dimension.ECOSYSTEM,
        "Apple Home (HomeKit)",
        (
            "apple homekit",
            "apple homekit system",
            "homekit",
            "apple home",
            "apple home-kit",
            "apple home-kit®",
            "sprachsteuerung per apple homekit",
        ),
    ),
    CompatibilityTerm(
        "google_home", Dimension.ECOSYSTEM, "Google Home", ("google home", "googlehome", "google home app")
    ),
    CompatibilityTerm("google_nest", Dimension.ECOSYSTEM, "Google Nest", ("nest smart home system", "google nest")),
    CompatibilityTerm(
        "samsung_smartthings",
        Dimension.ECOSYSTEM,
        "Samsung SmartThings",
        ("samsung smartthings", "samsung smart things", "samsung smart things system", "smartthings"),
    ),
    CompatibilityTerm(
        "bosch_smart_home",
        Dimension.ECOSYSTEM,
        "Bosch Smart Home",
        ("bosch smart home", "bosch smart home system", "bosch smart home app"),
    ),
    CompatibilityTerm(
        "homematic_ip",
        Dimension.ECOSYSTEM,
        "Homematic IP",
        ("homematic ip", "homematic ip system", "homematic ip app"),
    ),
    CompatibilityTerm(
        "philips_hue",
        Dimension.ECOSYSTEM,
        "Philips Hue",
        (
            "philips hue",
            "philips hue system",
            "philips hue app",
            "app philips hue",
            "philips hue bluetooth app",
            "philips hue bridge",
        ),
    ),
    CompatibilityTerm(
        "ledvance_smart_plus",
        Dimension.ECOSYSTEM,
        "LEDVANCE SMART+",
        ("ledvance smart+", "ledvance smart+ system", "ledvance smart+ app", "ledvance smart+ wifi app"),
    ),
    CompatibilityTerm("ring", Dimension.ECOSYSTEM, "Ring", ("ring smart home system", "ring app")),
    CompatibilityTerm(
        "abus_smartvest", Dimension.ECOSYSTEM, "ABUS Smartvest", ("abus smartvest system", "smartvest pro-app")
    ),
    CompatibilityTerm(
        "smart_friends",
        Dimension.ECOSYSTEM,
        "Smart Friends",
        ("abus smart friends system", "smart friends system", "smart friends", "smart friends app"),
    ),
    CompatibilityTerm(
        "schellenberg_smart_home",
        Dimension.ECOSYSTEM,
        "Schellenberg Smart Home",
        ("schellenberg smart home system", "schellenberg smart home"),
    ),
    CompatibilityTerm(
        "gardena_smart_system",
        Dimension.ECOSYSTEM,
        "Gardena smart system",
        ("gardena smart system", "gardena smart gateway", "gardena smart"),
    ),
    CompatibilityTerm(
        "magenta_smarthome",
        Dimension.ECOSYSTEM,
        "Magenta SmartHome",
        ("magenta smart home system", "magenta smarthome", "magenta smart home"),
    ),
    CompatibilityTerm("wiz", Dimension.ECOSYSTEM, "WiZ", ("wiz system", "wiz", "wiz app")),
    CompatibilityTerm("eglo_connect", Dimension.ECOSYSTEM, "EGLO connect", ("eglo connect system", "eglo connect")),
    CompatibilityTerm("nuki", Dimension.ECOSYSTEM, "Nuki", ("nuki smart home", "nuki app")),
    CompatibilityTerm("velux_active", Dimension.ECOSYSTEM, "VELUX Smart Home", ("velux smart home system",)),
    CompatibilityTerm("arlo", Dimension.ECOSYSTEM, "Arlo", ("arlo smart system", "arlo app")),
    CompatibilityTerm("razer_chroma", Dimension.ECOSYSTEM, "Razer Chroma", ("razer chroma system", "razer chroma")),
    CompatibilityTerm(
        "essentials_smart_home",
        Dimension.ECOSYSTEM,
        "Essentials Smart Home",
        ("essentials smart home system", "essentials smart home app"),
    ),
    CompatibilityTerm("ifttt", Dimension.ECOSYSTEM, "IFTTT", ("ifttt", "ifttt system")),
    CompatibilityTerm("aqara_home", Dimension.ECOSYSTEM, "Aqara Home", ("aqara home",)),
    CompatibilityTerm(
        "tuya_smart_life",
        Dimension.ECOSYSTEM,
        "Tuya / Smart Life",
        ("tuya app", "smart life app", "tuya smart", "tuya smart app"),
    ),
    CompatibilityTerm("xiaomi_home", Dimension.ECOSYSTEM, "Xiaomi Home", ("mi home app", "xiaomi home", "mi home")),
    CompatibilityTerm(
        "shelly", Dimension.ECOSYSTEM, "Shelly", ("shelly cloud app", "shelly smart control app", "shelly app")
    ),
    # Voice assistants
    CompatibilityTerm(
        "amazon_alexa",
        Dimension.VOICE_ASSISTANT,
        "Amazon Alexa",
        (
            "amazon alexa",
            "alexa",
            "amazon alexa möglich",
            "amazon echo + app",
            "amazon echo dot + app",
            "amazon echo show + app",
            "amazon echo plus + app",
            "amazon echo",
            "amazon echo dot",
            "amazon echo show",
            "amazon echo plus",
        ),
    ),
    CompatibilityTerm("google_assistant", Dimension.VOICE_ASSISTANT, "Google Assistant", ("google assistant",)),
    CompatibilityTerm("apple_siri", Dimension.VOICE_ASSISTANT, "Apple Siri", ("apple siri", "siri")),
    # Transport protocols
    CompatibilityTerm("wifi", Dimension.PROTOCOL, "Wi-Fi", ("wlan", "wifi", "wi-fi", "w-lan")),
    CompatibilityTerm("zigbee", Dimension.PROTOCOL, "Zigbee", ("zigbee", "zigbee 3.0")),
    CompatibilityTerm("z_wave", Dimension.PROTOCOL, "Z-Wave", ("z-wave", "z-wave plus", "zwave")),
    CompatibilityTerm(
        "bluetooth", Dimension.PROTOCOL, "Bluetooth", ("bluetooth", "bluetooth le", "bluetooth low energy")
    ),
    CompatibilityTerm("thread", Dimension.PROTOCOL, "Thread", ("thread",)),
    CompatibilityTerm("ethernet", Dimension.PROTOCOL, "Ethernet (LAN)", ("lan", "ethernet")),
    CompatibilityTerm("dect", Dimension.PROTOCOL, "DECT", ("dect", "dect ule")),
    CompatibilityTerm("io_homecontrol", Dimension.PROTOCOL, "io-homecontrol", ("io-homecontrol",)),
    CompatibilityTerm("proprietary_rf", Dimension.PROTOCOL, "Proprietary radio (RF)", ("funk",)),
    # Mobile operating systems (companion apps)
    CompatibilityTerm("ios", Dimension.MOBILE_OS, "iOS", ("ios", "apple ios")),
    CompatibilityTerm("android", Dimension.MOBILE_OS, "Android", ("android",)),
)

# Version suffixes on mobile OS values ("iOS 8.0 oder höher") are dropped for lookup.
_OS_VERSION = re.compile(r"\s+\d+(\.\d+)*\s*(oder höher|or later|\+)?$", re.IGNORECASE)


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold().replace("™", "").replace("®", "").strip()


_BY_CANONICAL = {term.canonical: term for term in TERMS}
# Canonical ids that are valid in several dimensions do not exist; alias keys are unique per dimension.
# Keys are normalized like lookups, so aliases written with "®" or "™" still match.
_BY_ALIAS: dict[str, CompatibilityTerm] = {
    normalize_alias(alias): term for term in TERMS for alias in (*term.aliases, term.canonical)
}


def lookup(value: str) -> CompatibilityTerm | None:
    """Canonical term for a raw value, or None when there is no safe mapping."""
    key = normalize_alias(value)
    if key in _BY_ALIAS:
        return _BY_ALIAS[key]
    stripped = _OS_VERSION.sub("", key)
    term = _BY_ALIAS.get(stripped)
    if term is not None and term.dimension is Dimension.MOBILE_OS:
        return term
    return None


def term_by_canonical(canonical: str | None) -> CompatibilityTerm | None:
    return _BY_CANONICAL.get(canonical) if canonical else None


def label_for(canonical: str | None) -> str | None:
    term = term_by_canonical(canonical)
    return term.label if term else None


def surface_forms(canonical: str) -> tuple[str, ...]:
    """Strings that may legitimately appear in evidence mentioning this canonical value."""
    term = _BY_CANONICAL[canonical]
    forms = {normalize_alias(alias) for alias in term.aliases}
    forms.add(normalize_alias(term.label))
    # Short base names used in running text ("HomeKit", "SmartThings", "Hue").
    forms.update(_EXTRA_SURFACE_FORMS.get(canonical, ()))
    return tuple(sorted(forms))


_EXTRA_SURFACE_FORMS: dict[str, tuple[str, ...]] = {
    "apple_home": ("homekit", "apple home"),
    "samsung_smartthings": ("smartthings", "smart things"),
    "philips_hue": ("hue",),
    "wifi": ("wlan", "wi-fi", "wifi"),
    "z_wave": ("z-wave", "zwave"),
    "bluetooth": ("bluetooth",),
    "proprietary_rf": ("funk", "mhz"),
    "ethernet": ("lan", "ethernet"),
    "ledvance_smart_plus": ("smart+",),
}


def find_terms(text: str, dimension: Dimension) -> tuple[tuple[CompatibilityTerm, str], ...]:
    """Terms of one dimension named as whole words inside free text, with the matched text
    ("über Sprachsteuerung wie Google Assistant & Amazon Alexa" -> Google Assistant, Amazon Alexa)."""
    found: dict[str, tuple[CompatibilityTerm, str]] = {}
    for term in TERMS:
        if term.dimension is not dimension:
            continue
        for alias in sorted({normalize_alias(a) for a in (*term.aliases, term.label)}, key=len, reverse=True):
            pattern = r"\s+".join(map(re.escape, alias.split()))
            match = re.search(rf"(?<!\w){pattern}(?!\w)", text, re.IGNORECASE)
            if match:
                found.setdefault(term.canonical, (term, match.group(0)))
                break
    return tuple(found.values())
