"""Free text -> canonical catalog ids. Everything goes through `Vocabulary`:

    Vocabulary.resolve_term("HomeKit")               # -> ResolvedTerm("apple_home", ECOSYSTEM, ...)
    Vocabulary.resolve_category("Heizkörperthermostat")  # -> "heating_control"
    Vocabulary.resolve_owned_device("Hue Bridge")    # -> "philips_hue_bridge"

Unknown or ambiguous input raises `TermResolutionError` (with `options` when ambiguous).
"""

from smart_home_agent.services.vocabulary.resolved_term import ResolvedTerm
from smart_home_agent.services.vocabulary.term_resolution_error import TermResolutionError
from smart_home_agent.services.vocabulary.vocabulary import Vocabulary

__all__ = ["ResolvedTerm", "TermResolutionError", "Vocabulary"]
