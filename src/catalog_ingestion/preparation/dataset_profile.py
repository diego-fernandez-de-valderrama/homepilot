from dataclasses import dataclass


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
