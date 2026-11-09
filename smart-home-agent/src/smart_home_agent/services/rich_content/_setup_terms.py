from collections.abc import Sequence

from smart_home_agent.models import CAPABILITY_DIMENSIONS, Product
from smart_home_agent.services.vocabulary import ResolvedTerm, TermResolutionError, Vocabulary


def known_terms(canonicals: Sequence[str]) -> list[ResolvedTerm]:
    """The canonical ids that are known terms, without duplicates (unknown ids are skipped)."""
    terms = []
    for canonical in dict.fromkeys(canonicals):
        try:
            terms.append(Vocabulary.term(canonical))
        except TermResolutionError:
            continue
    return terms


def own_terms(product: Product) -> list[ResolvedTerm]:
    """The capability terms the catalog states for the product (any status)."""
    return known_terms(
        [f.canonical_value for f in product.compatibility if f.canonical_value and f.dimension in CAPABILITY_DIMENSIONS]
    )
