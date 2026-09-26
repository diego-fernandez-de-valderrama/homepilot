"""Canonical requirement items (hubs, gateways, subscriptions, ...) and their text patterns."""

import re
from dataclasses import dataclass

from catalog_ingestion.domain.enums import RequirementKind


@dataclass(frozen=True, slots=True)
class RequirementTerm:
    canonical: str
    label: str
    kind: RequirementKind
    pattern: re.Pattern[str]


def _p(expression: str) -> re.Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


TERMS: tuple[RequirementTerm, ...] = (
    RequirementTerm(
        "bosch_smart_home_controller",
        "Bosch Smart Home Controller",
        RequirementKind.HUB,
        _p(r"(bosch )?smart home controller( ii)?"),
    ),
    RequirementTerm("homematic_ip_access_point", "Homematic IP Access Point", RequirementKind.HUB, _p(r"access point")),
    RequirementTerm("homematic_ccu3", "Homematic Zentrale CCU3", RequirementKind.HUB, _p(r"ccu ?3|ccu2/3|ccu2/ccu3")),
    RequirementTerm(
        "third_party_partner_solution",
        "Compatible third-party partner solution",
        RequirementKind.HUB,
        _p(r"partnerlösung"),
    ),
    RequirementTerm("standalone", "Stand-alone operation (no hub)", RequirementKind.OTHER, _p(r"stand-?alone")),
    RequirementTerm("philips_hue_bridge", "Philips Hue Bridge", RequirementKind.HUB, _p(r"hue bridge")),
    RequirementTerm(
        "ring_alarm_base_station", "Ring Alarm base station", RequirementKind.HUB, _p(r"ring alarm basisstation")
    ),
    RequirementTerm(
        "gardena_smart_gateway", "Gardena smart Gateway", RequirementKind.GATEWAY, _p(r"gardena smart gateway")
    ),
    RequirementTerm(
        "essentials_smart_home_hub",
        "Essentials Smart Home hub",
        RequirementKind.HUB,
        _p(r"essentials smart home zentrale"),
    ),
    RequirementTerm(
        "ring_subscription",
        "Ring subscription",
        RequirementKind.SUBSCRIPTION,
        _p(r"abonnement bei ring|ring home-abonnement|ring protect"),
    ),
    RequirementTerm("wifi_network", "Wi-Fi network", RequirementKind.NETWORK, _p(r"wlan|wi-?fi")),
    RequirementTerm("smartphone", "Smartphone or tablet", RequirementKind.DEVICE, _p(r"smartphone|tablet")),
    RequirementTerm("smart_hub", "Smart home hub (generic)", RequirementKind.HUB, _p(r"smart hub|gateway|zentrale")),
    RequirementTerm(
        "professional_installation",
        "Installation by a qualified electrician",
        RequirementKind.PROFESSIONAL_INSTALLATION,
        _p(r"fachhandwerker|elektrofachkraft|fachkraft"),
    ),
)

_BY_CANONICAL = {term.canonical: term for term in TERMS}


def match_terms(text: str) -> tuple[RequirementTerm, ...]:
    """All requirement terms mentioned in `text`, most specific first.

    The generic `smart_hub` term is only returned when no specific hub/gateway matched.
    """
    matched = [term for term in TERMS if term.pattern.search(text)]
    specific_hub = any(
        t.kind in (RequirementKind.HUB, RequirementKind.GATEWAY) and t.canonical != "smart_hub" for t in matched
    )
    if specific_hub:
        matched = [term for term in matched if term.canonical != "smart_hub"]
    return tuple(matched)


def lookup(item: str) -> RequirementTerm | None:
    """Best canonical term for a free-text requirement item."""
    matched = match_terms(item)
    return matched[0] if matched else None


def term_by_canonical(canonical: str | None) -> RequirementTerm | None:
    return _BY_CANONICAL.get(canonical) if canonical else None
