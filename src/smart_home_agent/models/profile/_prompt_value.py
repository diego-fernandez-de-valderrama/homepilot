import re
from typing import ClassVar

from smart_home_agent.models.profile.fact_kind import FactKind


class PromptValue:
    """How stored customer values are written into the system instruction."""

    _MAX_CHARS = 120
    _MARKUP = re.compile(r"[#`<>*\[\]|]+")  # "_" stays: canonical ids such as apple_home
    # Retracted facts the instruction still mentions, so the model does not assume them again.
    _NO_LONGER: ClassVar[dict[FactKind, str]] = {
        FactKind.ECOSYSTEM: "no longer uses",
        FactKind.HUB: "no longer owns",
        FactKind.OWNED_DEVICE: "no longer owns",
    }

    @classmethod
    def inline(cls, value: str) -> str:
        """A stored value as one short line of data: no line breaks, headings or markup, so a stored "preference"
        can never add sections or instructions to the system instruction."""
        text = cls._MARKUP.sub(" ", " ".join(value.split())).replace('"', "'")
        text = " ".join(text.split())
        return text if len(text) <= cls._MAX_CHARS else text[: cls._MAX_CHARS - 3].rstrip() + "..."

    @classmethod
    def no_longer(cls, kind: FactKind) -> str | None:
        """The phrase for a retracted fact of this kind, None when a retraction is not mentioned."""
        return cls._NO_LONGER.get(kind)
