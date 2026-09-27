from collections.abc import Sequence

from smart_home_agent.models import CAPABILITY_DIMENSIONS, NOT_LISTED, ComparisonResult, Product
from smart_home_agent.services.comparison._rows import price, requirements, row, spec_value, status_text
from smart_home_agent.services.vocabulary import Vocabulary


class ProductComparer:
    """Builds the comparison table of already loaded products (no catalog access)."""

    MIN_PRODUCTS = 2
    MAX_PRODUCTS = 4

    @staticmethod
    def compare(products: Sequence[Product]) -> ComparisonResult:
        rows = [
            row("general", "price", products, price),
            row(
                "general", "original price", products, lambda p: f"{p.original_price:.2f}" if p.original_price else None
            ),
            row("general", "brand", products, lambda p: p.brand),
            row("general", "category", products, lambda p: p.category_label_en or p.category),
            row("general", "product type", products, lambda p: p.product_type),
            row("general", "data completeness", products, lambda p: p.completeness_level),
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
            row("compatibility", Vocabulary.label(c), products, lambda p, c=c: status_text(p, c)) for c in canonicals
        )
        rows.append(row("requirements", "requirements", products, requirements))
        rows.append(
            row(
                "requirements",
                "professional installation",
                products,
                lambda p: "required" if p.requires_professional_installation else None,
            )
        )

        spec_names = list(dict.fromkeys(s.name for p in products for s in p.specs if s.name.casefold() != "ean"))
        rows.extend(row("specs", name, products, lambda p, n=name: spec_value(p, n)) for name in spec_names)

        supported = {p.id: p.supported_values() for p in products}
        only_supported_by = {
            p.id: sorted(
                Vocabulary.label(c)
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
            notes.append(f"Lowest price: {cheapest.title} ({price(cheapest)}).")

        return ComparisonResult(
            products=[p.summary() for p in products],
            rows=rows,
            key_features={p.id: p.key_features for p in products},
            only_supported_by=only_supported_by,
            notes=notes,
        )
