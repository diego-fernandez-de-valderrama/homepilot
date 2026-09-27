from typing import ClassVar

from catalog_ingestion.vocabulary._brands import BRAND_NORMALIZATION, KNOWN_BRANDS


class BrandVocabulary:
    """Brands seen in the catalog titles; a sub-brand is stored as its manufacturer brand."""

    KNOWN_BRANDS: ClassVar[tuple[str, ...]] = KNOWN_BRANDS

    @staticmethod
    def detect(title: str) -> str | None:
        """Brand from the start of the title, only when it is a known brand.

        Returns None for titles without a leading brand (e.g. "Überwachungskamera HB8 2K+");
        the LLM may propose one later, subject to validation against the title.
        """
        folded = title.casefold()
        for brand in KNOWN_BRANDS:
            candidate = brand.casefold()
            if folded == candidate or folded.startswith(candidate + " "):
                return BRAND_NORMALIZATION.get(brand, brand)
        return None
