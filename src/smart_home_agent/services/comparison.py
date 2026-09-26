"""Structured comparison of 2-4 products using PostgreSQL data only (never retrieved text)."""

from collections.abc import Callable, Sequence

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models.comparison import NOT_LISTED, ComparisonResult, ComparisonRow, RowGroup
from smart_home_agent.models.product import CAPABILITY_DIMENSIONS, Product
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services import vocabulary
from smart_home_agent.services.compatibility import ProductNotFoundError, term_status

MIN_PRODUCTS = 2
MAX_PRODUCTS = 4


def _price(product: Product) -> str:
    return f"{product.price:.2f} {product.currency or ''}".strip() if product.price is not None else NOT_LISTED


def _row(
    group: RowGroup, attribute: str, products: Sequence[Product], value: Callable[[Product], str | None]
) -> ComparisonRow:
    values = [value(p) or NOT_LISTED for p in products]
    return ComparisonRow(group=group, attribute=attribute, values=values, differs=len(set(values)) > 1)


def _status_text(product: Product, canonical: str) -> str:
    status, _ = term_status(product, canonical)
    return (
        f"{status.value} (not listed)"
        if status is FactStatus.UNKNOWN and not product.facts_for(canonical)
        else status.value
    )


def _spec_value(product: Product, name: str) -> str | None:
    for spec in product.specs:
        if spec.name.casefold() == name.casefold():
            return f"{spec.value} {spec.unit}".strip() if spec.unit else spec.value
    return None


def _requirements(product: Product) -> str | None:
    if not product.requirements:
        return None
    return "; ".join(f"{r.label} ({r.necessity.value.replace('_', ' ')})" for r in product.requirements)


def compare(products: Sequence[Product]) -> ComparisonResult:
    rows = [
        _row("general", "price", products, _price),
        _row("general", "original price", products, lambda p: f"{p.original_price:.2f}" if p.original_price else None),
        _row("general", "brand", products, lambda p: p.brand),
        _row("general", "category", products, lambda p: p.category_label_en or p.category),
        _row("general", "product type", products, lambda p: p.product_type),
        _row("general", "data completeness", products, lambda p: p.completeness_level),
    ]

    canonicals = sorted(
        {
            f.canonical_value
            for p in products
            for f in p.compatibility
            if f.canonical_value and f.dimension in CAPABILITY_DIMENSIONS
        }
    )
    rows.extend(
        _row("compatibility", vocabulary.label(c), products, lambda p, c=c: _status_text(p, c)) for c in canonicals
    )
    rows.append(_row("requirements", "requirements", products, _requirements))
    rows.append(
        _row(
            "requirements",
            "professional installation",
            products,
            lambda p: "required" if p.requires_professional_installation else None,
        )
    )

    spec_names = list(dict.fromkeys(s.name for p in products for s in p.specs if s.name.casefold() != "ean"))
    rows.extend(_row("specs", name, products, lambda p, n=name: _spec_value(p, n)) for name in spec_names)

    supported = {p.id: p.supported_values() for p in products}
    only_supported_by = {
        p.id: sorted(
            vocabulary.label(c)
            for c in supported[p.id] - set().union(*(s for pid, s in supported.items() if pid != p.id))
        )
        for p in products
    }
    notes = [
        f"'{NOT_LISTED}' means the catalog has no value for that product; it is not a 'no'.",
        "Compatibility 'unknown' means the catalog does not say; it is not 'unsupported'.",
    ]
    priced = [p for p in products if p.price is not None]
    if len(priced) >= 2:
        cheapest = min(priced, key=lambda p: p.price or 0.0)
        notes.append(f"Lowest price: {cheapest.title} ({_price(cheapest)}).")

    return ComparisonResult(
        products=[p.summary() for p in products],
        rows=rows,
        key_features={p.id: p.key_features for p in products},
        only_supported_by=only_supported_by,
        notes=notes,
    )


class ComparisonService:
    def __init__(self, catalog: CatalogReader) -> None:
        self._catalog = catalog

    def compare(self, product_ids: Sequence[str]) -> ComparisonResult:
        ids = list(dict.fromkeys(product_ids))
        if not MIN_PRODUCTS <= len(ids) <= MAX_PRODUCTS:
            raise ValueError(f"compare between {MIN_PRODUCTS} and {MAX_PRODUCTS} distinct products")
        products = self._catalog.get_products(ids)
        missing = [pid for pid in ids if pid not in {p.id for p in products}]
        if missing:
            raise ProductNotFoundError(missing)
        return compare(products)
