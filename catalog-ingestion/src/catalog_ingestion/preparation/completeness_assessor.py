from catalog_ingestion.models import CompatibilityFact, CompletenessReport, NormalizedProduct
from catalog_ingestion.vocabulary import CompletenessLevel, Dimension


class CompletenessAssessor:
    """Completeness analysis: decides whether the product page must be fetched (`needs_web`)."""

    _COMPATIBILITY_DIMENSIONS = frozenset({Dimension.ECOSYSTEM, Dimension.VOICE_ASSISTANT, Dimension.PROTOCOL})

    @staticmethod
    def assess(product: NormalizedProduct, facts: tuple[CompatibilityFact, ...]) -> CompletenessReport:
        has_description = not product.description.is_empty
        has_attributes = not product.attributes.is_empty
        has_compatibility = any(fact.dimension in CompletenessAssessor._COMPATIBILITY_DIMENSIONS for fact in facts)

        reasons: list[str] = []
        if not has_description:
            reasons.append("missing_description")
        if not has_attributes:
            reasons.append("missing_attributes")
        if not has_compatibility and CompletenessAssessor._looks_smart(product):
            reasons.append("smart_product_without_compatibility_information")

        score = round(0.35 * has_description + 0.35 * has_attributes + 0.30 * has_compatibility, 2)
        if has_description and has_attributes and has_compatibility:
            level = CompletenessLevel.RICH
        elif not has_description and not has_attributes:
            level = CompletenessLevel.SPARSE
        else:
            level = CompletenessLevel.PARTIAL

        return CompletenessReport(
            score=score,
            level=level,
            has_description=has_description,
            has_attributes=has_attributes,
            has_compatibility=has_compatibility,
            needs_web=bool(reasons),
            reasons=tuple(reasons),
        )

    @staticmethod
    def _looks_smart(product: NormalizedProduct) -> bool:
        if product.is_smart_home:
            return True
        haystack = f"{product.category_slug or ''} {product.title}".casefold()
        return "smart" in haystack
