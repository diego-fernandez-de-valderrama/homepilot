"""Customer memory rules, enforced in code (the prompt only asks the model to follow them):

- a fact is stored only with a verbatim quote from the customer's current message, so cart contents, tool
  results and the model's own guesses can never become facts;
- quotes about other people (a friend, family, a gift) are rejected: only the customer's own facts are kept;
- ecosystems and voice assistants resolve to canonical ids (ambiguous input raises, as everywhere);
- hubs (bridges, gateways, access points, connectors) map to a canonical hub id only when that is safe,
  otherwise they keep the customer's wording. Owned hardware that maps to a hub is stored as a hub too, so
  the hubs are complete even when the model passes a bridge as an owned device.
"""

import re
from dataclasses import dataclass

from catalog_ingestion.domain.enums import Dimension

from smart_home_agent.models.profile import (
    SINGLE_VALUED,
    CustomerFact,
    CustomerProfile,
    CustomerSummary,
    FactKind,
    NewFact,
    ProfileUpdate,
    RejectedFact,
)
from smart_home_agent.repositories.profile import ProfileStore
from smart_home_agent.services import vocabulary
from smart_home_agent.services.vocabulary import TermResolutionError

_MAX_EVIDENCE = 500
_MAX_VALUE = 200

# Words that show a quote is about someone else (EN/DE), matched as whole words on the quote only, so
# "I'm buying it for my friend, I use Alexa myself" can still be stored with the quote "I use Alexa myself".
# Plain pronouns are not listed ("I have Hue lights, they work great" is the customer's own fact).
_THIRD_PARTY = re.compile(
    r"\b("
    r"friends?|girlfriend|boyfriend|gifts?|mum|mom|mother|dad|father|parents?|brother|sister|wife|husband|"
    r"partner|son|daughter|kids?|children|grand\w*|uncle|aunt|cousin|neighbou?rs?|colleagues?|boss|"
    r"roommate|flatmate|for (him|her|them)|"
    r"freund\w*|geschenk\w*|mutter|mama|vater|papa|eltern|bruder|schwester|frau|mann|sohn|tochter|kinder?|"
    r"oma|opa|onkel|tante|nachbar\w*|kolleg\w*|chef\w*|mitbewohner\w*|für (ihn|sie|ihre?n?)"
    r")\b",
    re.IGNORECASE,
)

_SPACES = re.compile(r"\s+")
_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "´": "'", "`": "'"})


def _normalize(text: str) -> str:
    return _SPACES.sub(" ", text.translate(_QUOTES)).strip().casefold()


def _clean(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(v.strip()[:_MAX_VALUE] for v in values or [] if v.strip()))


def _hub_id(value: str) -> str | None:
    """Canonical hub id when `value` names a specific hub, else None."""
    try:
        canonical = vocabulary.resolve_owned_device(value)
    except TermResolutionError:
        return None
    return canonical if vocabulary.is_hub(canonical) else None


class MemoryRuleError(ValueError):
    """The whole update is refused (missing, foreign or third-party evidence): nothing is stored."""


@dataclass(frozen=True, slots=True)
class _Retraction:
    kinds: tuple[FactKind, ...]
    text: str


# Kinds a "no longer owned" statement retracts: the customer does not say whether it was a hub.
_OWNED = (FactKind.HUB, FactKind.OWNED_DEVICE)


class ProfileService:
    def __init__(self, store: ProfileStore) -> None:
        self._store = store

    def profile(self, user_id: str, include_retracted: bool = False) -> CustomerProfile:
        return self._store.load(user_id, include_retracted)

    def customers(self) -> list[CustomerSummary]:
        return self._store.customers()

    def remember(
        self,
        user_id: str,
        session_id: str | None,
        user_message: str | None,
        evidence: str,
        *,
        name: str | None = None,
        language: str | None = None,
        ecosystems: list[str] | None = None,
        hubs: list[str] | None = None,
        owned_devices: list[str] | None = None,
        preferences: list[str] | None = None,
        no_longer_used: list[str] | None = None,
        no_longer_owned: list[str] | None = None,
    ) -> ProfileUpdate:
        quote = self._check_evidence(user_message, evidence)
        current = self._store.load(user_id)
        new: list[NewFact] = []
        rejected: list[RejectedFact] = []
        if name is not None and name.strip():
            new.append(NewFact(kind=FactKind.NAME, value=name.strip()[:_MAX_VALUE], label=name.strip()[:_MAX_VALUE]))
        if language is not None and language.strip():
            code = language.strip().lower()[:2]
            if code in {"en", "de"}:
                new.append(NewFact(kind=FactKind.LANGUAGE, value=code, canonical=code, label=language.strip()))
            else:
                rejected.append(RejectedFact(kind=FactKind.LANGUAGE, value=language, reason="only 'en' or 'de'"))
        new += self._ecosystems(_clean(ecosystems), rejected)
        new += [self._hub(value) for value in _clean(hubs)]
        new += [self._device(value) for value in _clean(owned_devices)]
        new += [NewFact(kind=FactKind.PREFERENCE, value=_normalize(p), label=p) for p in _clean(preferences)]

        retractions = [_Retraction((FactKind.ECOSYSTEM,), v) for v in _clean(no_longer_used)]
        retractions += [_Retraction(_OWNED, v) for v in _clean(no_longer_owned)]
        retract_ids, retract_rejected = self._retractions(current, retractions)
        rejected += retract_rejected

        active = {(f.kind, f.value): f for f in current.active()}
        to_add: list[NewFact] = []
        unchanged: list[str] = []
        for fact in {(f.kind, f.value): f for f in new}.values():
            if (fact.kind, fact.value) in active and active[(fact.kind, fact.value)].id not in retract_ids:
                unchanged.append(fact.value)
                continue
            if fact.kind in SINGLE_VALUED:  # the new value supersedes the previous one
                retract_ids += [f.id for f in current.active() if f.kind is fact.kind and f.id not in retract_ids]
            to_add.append(fact)

        added: list[CustomerFact] = []
        retracted: list[CustomerFact] = []
        if to_add or retract_ids:
            added, retracted = self._store.apply(user_id, session_id, quote, to_add, retract_ids)
        return ProfileUpdate(
            added=added,
            retracted=retracted,
            unchanged=unchanged,
            rejected=rejected,
            profile=self._store.load(user_id, include_retracted=True),
        )

    @staticmethod
    def _check_evidence(user_message: str | None, evidence: str) -> str:
        quote = _SPACES.sub(" ", evidence.translate(_QUOTES)).strip().strip("\"'").strip()
        if not quote:
            raise MemoryRuleError("evidence is required: quote the customer's own words from their latest message")
        if len(quote) > _MAX_EVIDENCE:
            raise MemoryRuleError("evidence is too long: quote only the sentence that states the fact")
        if not user_message or _normalize(quote) not in _normalize(user_message):
            raise MemoryRuleError(
                "evidence is not a verbatim quote of the customer's latest message: only facts the customer stated "
                "in this message can be remembered (never the cart, a tool result or an assumption)"
            )
        if _THIRD_PARTY.search(quote):
            raise MemoryRuleError(
                "the quote is about someone else (friend, family, gift): facts about other people are never stored"
            )
        return quote

    @staticmethod
    def _ecosystems(values: list[str], rejected: list[RejectedFact]) -> list[NewFact]:
        facts: list[NewFact] = []
        for value in values:
            resolved = vocabulary.resolve_term(value)  # ambiguous or unknown: TermResolutionError for the tool
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

    @staticmethod
    def _hub(value: str) -> NewFact:
        canonical = _hub_id(value)  # None: keep the customer's wording ("Zigbee bridge"), never guess a hub
        return NewFact(kind=FactKind.HUB, value=canonical or _normalize(value), canonical=canonical, label=value)

    @classmethod
    def _device(cls, value: str) -> NewFact:
        try:
            canonical: str | None = vocabulary.resolve_owned_device(value)
        except TermResolutionError:
            canonical = None  # no safe mapping: keep the customer's wording
        if canonical is not None and vocabulary.is_hub(canonical):
            return cls._hub(value)
        return NewFact(
            kind=FactKind.OWNED_DEVICE, value=canonical or _normalize(value), canonical=canonical, label=value
        )

    def _retractions(
        self, current: CustomerProfile, retractions: list[_Retraction]
    ) -> tuple[list[int], list[RejectedFact]]:
        ids: list[int] = []
        rejected: list[RejectedFact] = []
        for item in retractions:
            candidates = self._retraction_values(item)
            matches = [
                f
                for f in current.active()
                if f.kind in item.kinds and (f.value in candidates or _normalize(f.label) in candidates)
            ]
            if not matches:
                rejected.append(RejectedFact(kind=item.kinds[0], value=item.text, reason="not in the stored profile"))
            ids += [f.id for f in matches if f.id not in ids]
        return ids, rejected

    @staticmethod
    def _retraction_values(item: _Retraction) -> set[str]:
        values = {_normalize(item.text)}
        try:
            if FactKind.ECOSYSTEM in item.kinds:
                values.add(vocabulary.resolve_term(item.text).canonical)
            else:
                values.add(vocabulary.resolve_owned_device(item.text))
        except TermResolutionError:
            pass  # match on the customer's wording only
        return values
