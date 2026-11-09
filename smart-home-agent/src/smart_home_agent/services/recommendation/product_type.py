import re

from smart_home_agent.models import Product

_WORD = re.compile(r"[\wäöüß]{4,}", re.IGNORECASE)


class ProductType:
    """Word-level product type matching (words of 4+ letters, case-insensitive)."""

    @classmethod
    def matches_need(cls, product: Product, need: str) -> bool:
        """The need names the product type (e.g. "thermostat" vs a "Heating valve adapter")."""
        need_words = cls._words(need)
        return bool(need_words & (cls._words(product.product_type) | cls._words(product.title)))

    @classmethod
    def same(cls, a: Product, b: Product) -> bool:
        """Both products serve the same need: the words of the shorter product type are all contained in the
        longer one ("Radiator thermostat" ~ "Smart radiator thermostat", but not ~ "Room thermostat")."""
        words_a, words_b = cls._words(a.product_type), cls._words(b.product_type)
        if not words_a or not words_b:
            return False
        shorter, longer = sorted((words_a, words_b), key=len)
        return shorter <= longer

    @staticmethod
    def _words(text: str | None) -> set[str]:
        return {w.casefold() for w in _WORD.findall(text or "")}
