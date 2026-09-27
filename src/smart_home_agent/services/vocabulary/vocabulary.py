"""Maps what the user (or Gemini) says to the canonical catalog vocabulary.

The canonical terms, categories and requirement items are the ones defined by
`catalog-ingestion`; this package only adds conversational aliases that point to existing
canonical ids. Aliases never cross concepts: Siri is not HomeKit, Google Assistant is not
Google Home, Matter is not a transport protocol. Ambiguous input raises instead of guessing.
"""

from smart_home_agent.services.vocabulary import _categories, _overview, _owned_devices, _terms
from smart_home_agent.services.vocabulary._aliases import RELATED_NOT_EQUIVALENT
from smart_home_agent.services.vocabulary.resolved_term import ResolvedTerm


class Vocabulary:
    """The single entry point for vocabulary lookups (stateless; the tables live in the private modules)."""

    # Compatibility terms (ecosystem, voice assistant, protocol, mobile OS)

    @staticmethod
    def term(canonical: str) -> ResolvedTerm:
        """Canonical id -> term; raises `TermResolutionError` for an unknown id."""
        return _terms.term(canonical)

    @staticmethod
    def label(canonical: str) -> str:
        """Display label of a canonical term (the id itself when it is unknown)."""
        return _terms.label(canonical)

    @staticmethod
    def resolve_term(value: str) -> ResolvedTerm:
        """Free text ("HomeKit", "Google Home", "matter-kompatibel", "zigbee") -> canonical term."""
        return _terms.resolve_term(value)

    @staticmethod
    def resolve_terms(values: list[str] | None) -> list[ResolvedTerm]:
        """`resolve_term` for each non-blank value, without duplicates."""
        resolved = [_terms.resolve_term(v) for v in values or [] if v.strip()]
        return list({t.canonical: t for t in resolved}.values())

    @staticmethod
    def related_concepts(canonical: str) -> tuple[str, ...]:
        """Concepts users often confuse with `canonical`. Only for explanatory notes; they never change a status."""
        return RELATED_NOT_EQUIVALENT.get(canonical, ())

    @staticmethod
    def mentions_term(canonical: str, normalized_text: str) -> bool:
        """The text names the compatibility term (an ingestion surface form or a conversational alias)."""
        return _terms.mentions_term(canonical, normalized_text)

    # Categories

    @staticmethod
    def resolve_category(value: str) -> str:
        """Category key, English/German label, URL slug or an everyday word -> canonical category key."""
        return _categories.resolve_category(value)

    # Requirement items (hubs, gateways, owned devices)

    @staticmethod
    def resolve_owned_device(value: str) -> str:
        """Hub/gateway or device the user owns ("Hue Bridge", "Homematic Access Point") -> canonical requirement id.

        Generic hubs, other brands' access points or controllers and non-ownable items raise instead of
        guessing, so they never satisfy a product's hub requirement."""
        return _owned_devices.resolve_owned_device(value)

    @staticmethod
    def is_hub(canonical: str) -> bool:
        """True for a specific hub, bridge or gateway (not the generic one, a network, a phone or a subscription)."""
        return _owned_devices.is_hub(canonical)

    @staticmethod
    def requirement_label(canonical: str) -> str:
        return _owned_devices.requirement_label(canonical)

    @staticmethod
    def mentions_requirement(canonical: str, normalized_text: str) -> bool:
        return _owned_devices.mentions_requirement(canonical, normalized_text)

    # Prompt

    @staticmethod
    def overview() -> str:
        """Canonical vocabulary as plain text, for the system instruction."""
        return _overview.vocabulary_overview()
