"""Dataset profile: reproduces the dataset analysis documented in the README."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from catalog_ingestion.extraction.compatibility import extract_compatibility
from catalog_ingestion.extraction.requirements import extract_requirements
from catalog_ingestion.ingestion.zip_loader import load_products
from catalog_ingestion.normalization.normalizer import normalize
from catalog_ingestion.quality.completeness import assess_completeness


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    counts: dict[str, int]
    completeness_levels: dict[str, int]
    categories: dict[str, int]
    unmapped_category_slugs: dict[str, int]
    brands: dict[str, int]
    attribute_keys: dict[str, int]
    unmapped_compatibility_values: dict[str, int]
    requirements: dict[str, int]


def profile_dataset(zip_path: Path, top: int = 25) -> DatasetProfile:
    loaded = load_products(zip_path)
    counts: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    unmapped_slugs: Counter[str] = Counter()
    brands: Counter[str] = Counter()
    keys: Counter[str] = Counter()
    unmapped_values: Counter[str] = Counter()
    requirements: Counter[str] = Counter()

    counts["products"] = len(loaded.products)
    counts["load_errors"] = len(loaded.errors)
    for raw in loaded.products:
        product = normalize(raw)
        facts = extract_compatibility(product)
        report = assess_completeness(product, facts)
        counts["empty_description"] += product.description.is_empty
        counts["empty_attributes"] += product.attributes.is_empty
        counts["empty_description_and_attributes"] += product.description.is_empty and product.attributes.is_empty
        counts["empty_subtitle"] += not product.subtitle
        counts["no_variants"] += not product.variants
        counts["discounted_price"] += product.price.original_value is not None
        counts["unparsed_price"] += product.price.value is None
        counts["unparsed_attribute_lines"] += len(product.attributes.unparsed_lines)
        counts["smart_home_flag_ja"] += product.is_smart_home is True
        counts["no_brand_detected"] += product.brand is None
        counts["no_compatibility_facts"] += not report.has_compatibility
        counts["needs_web"] += report.needs_web
        levels[report.level.value] += 1
        categories[product.category or "(none)"] += 1
        if product.category is None:
            unmapped_slugs[product.category_slug or "(no slug)"] += 1
        brands[product.brand or "(none)"] += 1
        keys.update({entry.key for entry in product.attributes.entries})
        unmapped_values.update(f"{f.dimension.value}: {f.raw_value}" for f in facts if f.canonical_value is None)
        requirements.update(r.canonical_item or r.item for r in extract_requirements(product))

    return DatasetProfile(
        counts=dict(counts),
        completeness_levels=dict(levels),
        categories=dict(categories.most_common()),
        unmapped_category_slugs=dict(unmapped_slugs.most_common()),
        brands=dict(brands.most_common(top)),
        attribute_keys=dict(keys.most_common(top)),
        unmapped_compatibility_values=dict(unmapped_values.most_common(top)),
        requirements=dict(requirements.most_common()),
    )
