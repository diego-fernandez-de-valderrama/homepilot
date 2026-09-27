"""Checks on a finished model answer: empty (nothing usable) or stalled (announces work instead of doing it)."""

import re

from google.adk.models import LlmResponse
from google.genai import types

# Announcements of work still to come, in English and German. Matched only in a final answer without a tool call.
_ANNOUNCEMENT = re.compile(
    "|".join(
        (
            r"\b(give|allow) me a (moment|second|minute)\b",
            r"\b(one|just a|wait a) (moment|second|minute)\b",
            r"\bplease (wait|hold on|bear with me)\b",
            r"\blet me (now |quickly |just )?(search|look|check|find|get|pull)\b",
            r"\bI(?:'ll| will| am going to|'m going to)( now| quickly| just)? "
            r"(search|look|check|find|use this information)\b",
            r"\bI(?:'m| am) (now )?(searching|looking|checking)\b",
            r"\b(einen|einen kleinen|einen kurzen) (moment|augenblick)\b",
            r"\bmoment,? bitte\b",
            r"\bich (suche|schaue|prüfe|sehe) (jetzt|gleich|kurz|nun|sofort)\b",
            r"\b(ich werde|lass mich|lassen sie mich) (\w+ ){0,4}(suchen|prüfen|nachsehen|nachschauen|heraussuchen)\b",
        )
    ),
    re.IGNORECASE,
)


def announces_action(text: str) -> bool:
    """The answer promises work to come instead of a result (a closing question is an offer, not a promise)."""
    stripped = text.strip()
    return bool(stripped) and not stripped.endswith("?") and _ANNOUNCEMENT.search(stripped) is not None


def is_empty(response: LlmResponse) -> bool:
    """A finished answer without anything usable: no parts, or only thoughts (never shown to the customer)."""
    if response.partial or response.error_code is not None:
        return False
    if response.finish_reason not in (None, types.FinishReason.STOP):
        return False
    parts = response.content.parts if response.content else None
    return not any((part.text and not part.thought) or part.function_call for part in parts or [])


def is_stalled(response: LlmResponse) -> bool:
    """A finished answer without a tool call that only announces what the model is about to do."""
    if response.partial or response.error_code is not None or not response.content:
        return False
    parts = response.content.parts or []
    if any(part.function_call for part in parts):
        return False
    return announces_action("".join(part.text or "" for part in parts if not part.thought))
