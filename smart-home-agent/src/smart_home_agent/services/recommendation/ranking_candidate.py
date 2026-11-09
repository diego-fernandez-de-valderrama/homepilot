from dataclasses import dataclass

from smart_home_agent.models import Product


@dataclass(slots=True)
class RankingCandidate:
    product: Product
    relevance: float  # semantic similarity, normalized to the best candidate (0..1)
    type_match: bool
    capabilities: frozenset[str]  # confirmed canonical ecosystems, voice assistants and protocols
    upgrade_capabilities: frozenset[str] = frozenset()  # `capabilities` plus confirmed mobile OS (upsell only)
    needed_hubs: frozenset[str] = frozenset()  # required hubs that are missing or unverified
    uses_owned_hub: bool = False  # the catalog names a hub for it that the customer owns
    score: float = 0.0
