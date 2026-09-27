"""Requirement items (hubs, gateways, devices): what a customer owns and what a product needs."""

import re

from catalog_ingestion.domain.enums import RequirementKind
from catalog_ingestion.vocabulary import requirements as requirement_vocabulary

from smart_home_agent.services.vocabulary._aliases import key
from smart_home_agent.services.vocabulary.term_resolution_error import TermResolutionError

# Requirement ids a customer cannot "own": generic or non-device items. Owning "a hub" says nothing about
# which hub a product needs, and "standalone" is a product property, not a device.
NOT_OWNABLE = frozenset({"smart_hub", "standalone", "third_party_partner_solution", "professional_installation"})
# The catalog patterns of these hubs are written for product text, where the brand is implied
# ("Access Point" on a Homematic product). In what a customer says, the brand must be named:
# a "WLAN Access Point" or an "Aqara smart home controller" is not one of them.
_OWNED_BRAND = {
    "homematic_ip_access_point": re.compile(r"homematic|hmip", re.IGNORECASE),
    "bosch_smart_home_controller": re.compile(r"bosch", re.IGNORECASE),
}


def resolve_owned_device(value: str) -> str:
    """Hub/gateway or device the user owns ("Hue Bridge", "Homematic Access Point") -> canonical requirement id.

    Generic hubs, other brands' access points or controllers and non-ownable items raise instead of
    guessing, so they never satisfy a product's hub requirement."""
    normalized = key(value)
    if requirement_vocabulary.term_by_canonical(normalized) and normalized not in NOT_OWNABLE:
        return normalized
    # "Hue-Bridge" is the usual German spelling of "Hue Bridge".
    found = requirement_vocabulary.lookup(value) or requirement_vocabulary.lookup(value.replace("-", " "))
    if found is None or found.canonical in NOT_OWNABLE:
        raise TermResolutionError("owned device", value)
    brand = _OWNED_BRAND.get(found.canonical)
    if brand is not None and not brand.search(value):
        raise TermResolutionError("owned device", value)
    return found.canonical


def is_hub(canonical: str) -> bool:
    """True for a specific hub, bridge or gateway (not the generic one, a network, a phone or a subscription)."""
    found = requirement_vocabulary.term_by_canonical(canonical)
    return (
        found is not None
        and found.kind in (RequirementKind.HUB, RequirementKind.GATEWAY)
        and found.canonical != "smart_hub"
    )


def requirement_label(canonical: str) -> str:
    found = requirement_vocabulary.term_by_canonical(canonical)
    if found:
        return found.label
    return "Stand-alone operation (no hub)" if canonical == "standalone" else canonical


def mentions_requirement(canonical: str, normalized_text: str) -> bool:
    found = requirement_vocabulary.term_by_canonical(canonical)
    return found is not None and bool(found.pattern.search(normalized_text.replace("-", " ")))
