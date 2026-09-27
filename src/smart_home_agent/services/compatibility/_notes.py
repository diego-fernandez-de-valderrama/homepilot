"""Explanatory notes for an `unknown` term. They never change a status."""

from catalog_ingestion.vocabulary.compatibility import surface_forms

from smart_home_agent.models import Product
from smart_home_agent.services.vocabulary import ResolvedTerm, Vocabulary


def related_notes(product: Product, resolved: ResolvedTerm) -> list[str]:
    supported = product.supported_values()
    return [
        f"The product supports {Vocabulary.label(related)}, which is a different concept and does not "
        f"confirm {resolved.label}."
        for related in Vocabulary.related_concepts(resolved.canonical)
        if related in supported
    ]


def unmapped_mentions(product: Product, resolved: ResolvedTerm) -> list[str]:
    forms = surface_forms(resolved.canonical)
    return [
        f"Unmapped catalog mention {fact.raw_value!r} may refer to {resolved.label}; it is not a confirmation."
        for fact in product.compatibility
        if fact.canonical_value is None and any(form in fact.raw_value.casefold() for form in forms)
    ]
