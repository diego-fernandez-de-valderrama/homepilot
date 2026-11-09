"""Kinds of deterministic replies: one per blocking category, plus the output-check fallback."""

from enum import StrEnum


class ResponseType(StrEnum):
    ELECTRICAL = "ELECTRICAL"
    OFF_TOPIC = "OFF_TOPIC"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    OUTPUT_FALLBACK = "OUTPUT_FALLBACK"
