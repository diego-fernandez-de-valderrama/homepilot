"""Customer memory: facts a customer stated about themself, kept per user id across conversations."""

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FactKind(StrEnum):
    NAME = "name"
    LANGUAGE = "language"
    ECOSYSTEM = "ecosystem"  # ecosystems and voice assistants the customer uses (canonical ids)
    HUB = "hub"  # bridges, hubs, gateways, access points, connectors (canonical hub id when it maps safely)
    OWNED_DEVICE = "owned_device"  # other smart home hardware the customer owns, in their wording
    PREFERENCE = "preference"  # lasting preferences, free text


# Kinds with one value at a time: a new fact supersedes the previous one.
SINGLE_VALUED = frozenset({FactKind.NAME, FactKind.LANGUAGE})
# Retracted facts the instruction still mentions, so the model does not assume them again.
_NO_LONGER = {
    FactKind.ECOSYSTEM: "no longer uses",
    FactKind.HUB: "no longer owns",
    FactKind.OWNED_DEVICE: "no longer owns",
}


class CustomerFact(BaseModel):
    id: int
    user_id: str
    kind: FactKind
    value: str  # canonical id when `canonical` is set, else the normalized customer wording
    canonical: str | None = None  # None = no safe mapping to the vocabulary
    label: str  # the customer's own wording
    evidence: str  # verbatim quote from the customer's message
    session_id: str | None = None
    created_at: datetime
    active: bool = True
    retracted_at: datetime | None = None
    retracted_evidence: str | None = None


class NewFact(BaseModel):
    """A fact to store (before it has an id)."""

    kind: FactKind
    value: str
    canonical: str | None = None
    label: str


_PROMPT_VALUE_CHARS = 120
_MARKUP = re.compile(r"[#`<>*\[\]|]+")  # "_" stays: canonical ids such as apple_home


def _inline(value: str) -> str:
    """A stored value as one short line of data: no line breaks, headings or markup, so a stored "preference"
    can never add sections or instructions to the system instruction."""
    text = _MARKUP.sub(" ", " ".join(value.split())).replace('"', "'")
    text = " ".join(text.split())
    return text if len(text) <= _PROMPT_VALUE_CHARS else text[: _PROMPT_VALUE_CHARS - 3].rstrip() + "..."


class CustomerProfile(BaseModel):
    user_id: str
    facts: list[CustomerFact] = Field(default_factory=list)

    def active(self) -> list[CustomerFact]:
        return [f for f in self.facts if f.active]

    def prompt_lines(self) -> list[str]:
        """Facts for the system instruction: active ones with the customer's wording, then what the customer no
        longer owns or uses. Evidence quotes are left out on purpose: a quote can mention a fact that was
        retracted later ("I use HomeKit and have a Hue Bridge"), and the model would read it as current."""
        active = self.active()
        lines = [
            f"- {f.kind.value}: {_inline(f.value)}"
            + (f' ("{_inline(f.label)}")' if f.label.casefold() != f.value.casefold() else "")
            for f in active
        ]
        current = {(f.kind, f.value) for f in active}
        gone = dict.fromkeys(
            (f.kind, f.value)
            for f in self.facts
            if not f.active and f.kind in _NO_LONGER and (f.kind, f.value) not in current
        )
        lines += [
            f"- {_NO_LONGER[kind]}: {_inline(value)} (the customer said so: do not assume it)" for kind, value in gone
        ]
        return lines


class CustomerSummary(BaseModel):
    """A customer with something stored, for picking test customers in the interface."""

    user_id: str
    active_facts: int
    total_facts: int
    last_activity: datetime


class RejectedFact(BaseModel):
    kind: FactKind | None = None
    value: str | None = None
    reason: str


class ProfileUpdate(BaseModel):
    added: list[CustomerFact] = Field(default_factory=list)
    retracted: list[CustomerFact] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)  # values that were already stored
    rejected: list[RejectedFact] = Field(default_factory=list)
    profile: CustomerProfile
