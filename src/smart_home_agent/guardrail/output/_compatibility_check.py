"""unsupported_compatibility: a positive "works with X" claim about a product whose catalog facts do not support X
(PostgreSQL facts, never the model's wording or Qdrant)."""

import re
from collections.abc import Mapping, Sequence

from catalog_ingestion.domain.enums import Dimension, FactStatus

from smart_home_agent.guardrail.output._compatibility_terms import terms_in
from smart_home_agent.guardrail.output.product_lookup import ProductLookup
from smart_home_agent.guardrail.output.violation import Violation
from smart_home_agent.models import Product

# Compatibility: positive claims only; hedged or negated sentences are left to the model's wording.
_CLAIM = re.compile(
    r"\b(works? with|compatible with|supports?|integrates? with|controllable (via|with)|funktioniert mit"
    r"|kompatibel mit|unterstützt|lässt sich (mit|über)|steuerbar (mit|über))\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"\b(not|no|n't|cannot|unknown|unclear|confirm|verify|may|might|if|whether|nicht|kein|keine|unbekannt"
    r"|bestätigen|möglicherweise|ob)\b",
    re.IGNORECASE,
)


class CompatibilityCheck:
    def __init__(self, catalog: ProductLookup) -> None:
        self._catalog = catalog

    def check(
        self, sentences: Sequence[str], tool_products: Mapping[str, str], session_product_ids: Sequence[str]
    ) -> list[Violation]:
        candidates = [
            (s, terms) for s in sentences if _CLAIM.search(s) and not _HEDGE.search(s) if (terms := terms_in(s))
        ]
        if not candidates:
            return []
        titles = dict(tool_products)
        extra = [pid for pid in dict.fromkeys(session_product_ids) if not titles.get(pid)]
        if extra:  # only fetched when the answer contains a positive claim
            titles.update({p.id: p.title for p in self._catalog.get_products(extra)})
        claims: list[tuple[str, set[str], set[str]]] = []  # sentence, product ids, canonical terms
        for sentence, terms in candidates:
            folded = sentence.casefold()
            products = {
                pid
                for pid, title in titles.items()
                if pid in sentence or (len(title) >= 8 and title.casefold() in folded)
            }
            if products:
                claims.append((sentence, products, terms))
        if not claims:
            return []
        catalog = {p.id: p for p in self._catalog.get_products(sorted({pid for _, ids, _ in claims for pid in ids}))}
        violations = []
        for sentence, product_ids, terms in claims:
            linked = [catalog[pid] for pid in product_ids if pid in catalog]
            for canonical in terms:
                if linked and not self._claim_holds(linked, canonical):
                    violations.append(
                        Violation(kind="unsupported_compatibility", detail=f"{canonical}: {sentence[:160]}")
                    )
        return violations

    @staticmethod
    def _claim_holds(products: Sequence[Product], canonical: str) -> bool:
        """At least one linked product supports the term and none has explicit negative evidence."""
        supports = any(canonical in p.supported_values(tuple(Dimension)) for p in products)
        contradicted = any(f.status is FactStatus.UNSUPPORTED for p in products for f in p.facts_for(canonical))
        return supports and not contradicted
