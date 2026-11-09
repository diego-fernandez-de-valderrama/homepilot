from smart_home_agent.models import EvidenceResult, Product
from smart_home_agent.services.evidence._sources import CATALOG_FIELDS, FIELD_ALIASES, attribute, catalog_field
from smart_home_agent.services.vocabulary import TermResolutionError, Vocabulary


class EvidenceLookup:
    """Where one fact or field of a loaded product comes from (no catalog access)."""

    TOPICS_HELP = (
        "a compatibility term (e.g. 'Matter', 'HomeKit', 'Zigbee'), 'requirements', a field "
        "(price, title, brand, category, product_type, summary, key_features, use_cases, specs) or a catalog "
        "attribute name"
    )

    @staticmethod
    def for_product(product: Product, topic: str) -> EvidenceResult:
        """Tried in order: requirements, a verbatim catalog field, stored provenance, a catalog attribute, and
        finally a compatibility term (an unknown topic raises `TermResolutionError`)."""
        key = topic.strip().casefold()
        result = EvidenceResult(product_id=product.id, title=product.title, topic=topic, items=[], provenance=[])

        if key in ("requirements", "requirement", "anforderungen"):
            result.items = [r.evidence for r in product.requirements]
            result.note = None if result.items else "The catalog lists no requirements for this product."
            return result
        if key in CATALOG_FIELDS:
            result.items = catalog_field(product, key)
            return result
        fields = FIELD_ALIASES.get(key, (key,))
        provenance = [p for p in product.provenance if p.field in fields]
        if provenance:
            result.provenance = provenance
            return result
        attributes = attribute(product, key)
        if attributes:
            result.items = attributes
            return result
        try:
            resolved = Vocabulary.resolve_term(topic)
        except TermResolutionError as exc:
            if exc.options:
                raise
            raise TermResolutionError("evidence topic", topic, []) from exc
        result.items = [fact.evidence for fact in product.facts_for(resolved.canonical)]
        if not result.items:
            result.note = (
                f"The catalog has no evidence about {resolved.label} for this product: its compatibility is unknown."
            )
        return result
