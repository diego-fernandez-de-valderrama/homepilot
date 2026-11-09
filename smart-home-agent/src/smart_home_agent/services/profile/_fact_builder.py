"""The tool arguments -> candidate facts, each resolved to a canonical id when that is safe."""

from catalog_ingestion.core import TextNormalizer
from catalog_ingestion.vocabulary import Dimension

from smart_home_agent.models import FactKind, NewFact, RejectedFact
from smart_home_agent.services.profile._text import MAX_VALUE
from smart_home_agent.services.vocabulary import TermResolutionError, Vocabulary

# Kinds a "no longer owned" statement retracts, and kinds an owned hardware value is backed by: the customer does
# not say whether it was a hub.
OWNED_KINDS = (FactKind.HUB, FactKind.OWNED_DEVICE)


def name_fact(name: str) -> NewFact:
    return NewFact(kind=FactKind.NAME, value=name.strip()[:MAX_VALUE], label=name.strip()[:MAX_VALUE])


def language_fact(language: str, rejected: list[RejectedFact]) -> list[NewFact]:
    code = language.strip().lower()[:2]
    if code in {"en", "de"}:
        return [NewFact(kind=FactKind.LANGUAGE, value=code, canonical=code, label=language.strip())]
    rejected.append(RejectedFact(kind=FactKind.LANGUAGE, value=language, reason="only 'en' or 'de'"))
    return []


def ecosystem_facts(values: list[str], rejected: list[RejectedFact]) -> list[NewFact]:
    facts: list[NewFact] = []
    for value in values:
        resolved = Vocabulary.resolve_term(value)  # ambiguous or unknown: TermResolutionError for the tool
        if resolved.dimension in (Dimension.PROTOCOL, Dimension.MOBILE_OS):
            rejected.append(
                RejectedFact(
                    kind=FactKind.ECOSYSTEM,
                    value=value,
                    reason=f"{resolved.label} is a {resolved.dimension.value}, not an ecosystem or voice assistant",
                )
            )
            continue
        facts.append(
            NewFact(kind=FactKind.ECOSYSTEM, value=resolved.canonical, canonical=resolved.canonical, label=value)
        )
    return facts


def hub_fact(value: str) -> NewFact:
    canonical = _hub_id(value)  # None: keep the customer's wording ("Zigbee bridge"), never guess a hub
    return NewFact(
        kind=FactKind.HUB, value=canonical or TextNormalizer.normalize(value), canonical=canonical, label=value
    )


def device_fact(value: str) -> NewFact:
    """An owned device; one that maps to a specific hub is stored as a hub."""
    try:
        canonical: str | None = Vocabulary.resolve_owned_device(value)
    except TermResolutionError:
        canonical = None  # no safe mapping: keep the customer's wording
    if canonical is not None and Vocabulary.is_hub(canonical):
        return hub_fact(value)
    return NewFact(
        kind=FactKind.OWNED_DEVICE, value=canonical or TextNormalizer.normalize(value), canonical=canonical, label=value
    )


def preference_fact(value: str) -> NewFact:
    return NewFact(kind=FactKind.PREFERENCE, value=TextNormalizer.normalize(value), label=value)


def _hub_id(value: str) -> str | None:
    """Canonical hub id when `value` names a specific hub, else None."""
    try:
        canonical = Vocabulary.resolve_owned_device(value)
    except TermResolutionError:
        return None
    return canonical if Vocabulary.is_hub(canonical) else None
