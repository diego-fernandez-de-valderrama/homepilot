"""unknown_product: a product id (in prose or in an answer tag) that is neither in this turn's tool results nor in
the catalog."""

import re
from collections.abc import Mapping

from smart_home_agent.answer_tags import TagParser
from smart_home_agent.guardrail.output.product_lookup import ProductLookup
from smart_home_agent.guardrail.output.violation import Violation

# Exactly 8 digits: never the first 8 digits of a longer number ("EAN 123456789"), a decimal or a digit group.
_PRODUCT_ID = re.compile(r"(?<![\d.,])\d{8}(?!\d|[.,]\d)")


class UnknownProductCheck:
    def __init__(self, catalog: ProductLookup) -> None:
        self._catalog = catalog

    def check(self, text: str, tool_products: Mapping[str, str]) -> list[Violation]:
        # Tag id lists ("ID,ID") are read from the parsed tags: the prose pattern skips comma-adjacent numbers.
        ids = [*_PRODUCT_ID.findall(text), *TagParser.referenced_ids(TagParser.parse(text))]
        mentioned = [pid for pid in dict.fromkeys(ids) if pid not in tool_products]
        if not mentioned:
            return []
        known = {p.id for p in self._catalog.get_products(mentioned)}
        return [Violation(kind="unknown_product", detail=pid) for pid in mentioned if pid not in known]
