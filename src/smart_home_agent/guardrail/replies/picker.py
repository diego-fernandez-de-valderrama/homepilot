"""Picks the reply text; the variant used last in the session is never picked twice in a row."""

import random

from smart_home_agent.guardrail.replies.pools import DEFAULT_LANGUAGE, RESPONSES
from smart_home_agent.guardrail.replies.response_type import ResponseType


def pick_response(
    kind: ResponseType, language: str | None, previous: str | None = None, rng: random.Random | None = None
) -> str:
    """A random variant of the pool for `kind` in `language` (default English), never `previous`."""
    pool = RESPONSES[kind].get(language or DEFAULT_LANGUAGE) or RESPONSES[kind][DEFAULT_LANGUAGE]
    candidates = [text for text in pool if text != previous] or list(pool)
    return (rng or random).choice(candidates)
