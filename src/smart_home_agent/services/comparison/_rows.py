"""Cell values of the comparison table. A missing value is `NOT_LISTED`, never a "no"."""

from collections.abc import Callable, Sequence

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models import NOT_LISTED, ComparisonRow, Product, RowGroup
from smart_home_agent.services.compatibility import CompatibilityEvaluator


def row(
    group: RowGroup, attribute: str, products: Sequence[Product], value: Callable[[Product], str | None]
) -> ComparisonRow:
    values = [value(p) or NOT_LISTED for p in products]
    return ComparisonRow(group=group, attribute=attribute, values=values, differs=len(set(values)) > 1)


def price(product: Product) -> str:
    return f"{product.price:.2f} {product.currency or ''}".strip() if product.price is not None else NOT_LISTED


def status_text(product: Product, canonical: str) -> str:
    status, _ = CompatibilityEvaluator.term_status(product, canonical)
    return (
        f"{status.value} (not listed)"
        if status is FactStatus.UNKNOWN and not product.facts_for(canonical)
        else status.value
    )


def spec_value(product: Product, name: str) -> str | None:
    for spec in product.specs:
        if spec.name.casefold() == name.casefold():
            return f"{spec.value} {spec.unit}".strip() if spec.unit else spec.value
    return None


def requirements(product: Product) -> str | None:
    if not product.requirements:
        return None
    return "; ".join(f"{r.label} ({r.necessity.value.replace('_', ' ')})" for r in product.requirements)
