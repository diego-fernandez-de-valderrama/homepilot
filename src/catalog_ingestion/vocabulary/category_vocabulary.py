from typing import ClassVar

from catalog_ingestion.vocabulary._categories import BRAND_PAGE_SLUGS, CATEGORIES
from catalog_ingestion.vocabulary.category import Category


class CategoryVocabulary:
    """Canonical product categories derived from the bauhaus.info URL category slug.

    The category only exists in the product URL (`/<category-slug>/<name-slug>/p/<id>`).
    Some slugs are brand landing pages (`BRAND_PAGE_SLUGS`, e.g. `shelly-smart-home`); they map to no
    category and the LLM picks one from `KEYS` instead.
    """

    CATEGORIES: ClassVar[tuple[Category, ...]] = CATEGORIES
    KEYS: ClassVar[tuple[str, ...]] = tuple(category.key for category in CATEGORIES)
    BRAND_PAGE_SLUGS: ClassVar[frozenset[str]] = BRAND_PAGE_SLUGS

    @staticmethod
    def for_slug(slug: str | None) -> Category | None:
        return _BY_SLUG.get(slug) if slug else None

    @staticmethod
    def by_key(key: str | None) -> Category | None:
        return _BY_KEY.get(key) if key else None


_BY_KEY = {category.key: category for category in CATEGORIES}
_BY_SLUG = {slug: category for category in CATEGORIES for slug in category.slugs}
