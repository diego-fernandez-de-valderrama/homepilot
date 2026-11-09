"""Splits an answer into the units the sentence-level checks look at."""

import re

_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")  # lines keep "Title (id): works with X" together


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCES.split(text) if s.strip()]
