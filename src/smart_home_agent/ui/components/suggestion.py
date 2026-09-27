from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Suggestion:
    """A welcome tile: an example request the customer can send with one click."""

    icon: str  # Material Symbols name, e.g. "thermostat"
    kicker: str  # short topic label above the title
    title: str
    prompt: str  # sent to the agent as the user's message
