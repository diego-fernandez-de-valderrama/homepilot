"""Deterministic checks of the final answer (no second model).

Every check is conservative: it only flags what it can show to be wrong, because a failed check
replaces the whole answer with a fallback. Unknown stays unknown: a claim that cannot be linked to a
product, or a term that cannot be resolved, passes.

- electrical: practical wiring / mains installation steps (EN/DE patterns, refusals excluded);
- unknown_product: a product id that is neither in this turn's tool results nor in the catalog;
- unsupported_compatibility: a positive "works with X" claim about a product whose catalog facts do
  not support X (PostgreSQL facts, never the model's wording or Qdrant);
- prompt_leak: internal tool names or verbatim lines of the system instruction;
- off_topic: only for answers produced without any tool, one embedding call against the prototypes.
"""

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from catalog_ingestion.domain.enums import Dimension, FactStatus
from catalog_ingestion.vocabulary import compatibility as compatibility_vocabulary
from pydantic import BaseModel

from smart_home_agent.guardrail.categories import Category
from smart_home_agent.guardrail.classifier import SemanticGuardrail
from smart_home_agent.models.product import Product
from smart_home_agent.repositories.postgres import CatalogReader

logger = logging.getLogger(__name__)

ViolationKind = Literal["electrical", "unknown_product", "unsupported_compatibility", "prompt_leak", "off_topic"]


class Violation(BaseModel):
    kind: ViolationKind
    detail: str


_PRODUCT_ID = re.compile(r"(?<![\d.,])\d{8}(?![\d.,]\d)")
_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")  # lines keep "Title (id): works with X" together

# Electrical: an instruction verb together with an electrical conductor/terminal term in one sentence.
_WIRE_TERMS = re.compile(
    r"\b(live|neutral|earth|ground|phase)\s+(wire|conductor|cable|lead|terminal)s?\b"
    r"|\b(brown|blue|black|grey|gray|green[- /]yellow|red)\s+(wire|cable|conductor|core)s?\b"
    r"|\bterminals?\s+(L|N|PE|L1|COM|NO)\b|\b(L|N|PE)\s+terminal\b|\bjunction box\b|\bmains\s+(cable|wire|supply)\b"
    r"|\bneutralleiter|\baußenleiter|\bschutzleiter|\bnullleiter|\bphase\b|\badern?\b|\bklemmen?\b"
    r"|\b(braune|blaue|schwarze|graue|grün-gelbe)[nsr]?\s+(ader|kabel|leiter|draht)\b|\bunterputzdose\b|\babzweigdose\b",
    re.IGNORECASE,
)
_INSTRUCTION = re.compile(
    r"(^|[\s(\d.\-*•])(connect|attach|screw|insert|strip|twist|clamp|wire|hook up|join|disconnect)"
    r"\s+(the|it|both|each|your)\b"
    r"|\b(schließen|klemmen|verbinden|verdrahten|isolieren|stecken|schrauben|drehen)\s+sie\b"
    r"|\b(schließe|verbinde|verdrahte|isoliere)\b|\bklemme\s+(die|den|das)\b"
    r"|\b(anschließen|anklemmen|abisolieren|verdrahten)\s*[.:,]"
    r"|\b(switch|turn)\s+off\s+the\s+(circuit\s+)?(breaker|fuse)\b|\bsicherung\s+(aus|raus|herausdrehen|abschalten)",
    re.IGNORECASE,
)
_REFUSAL = re.compile(
    r"\b(can't|cannot|can not|won't|unable|not able|don't|do not|never|electrician|elektrofachkraft|elektriker"
    r"|kann ich (leider )?nicht|keine anleitung|nicht selbst)\b",
    re.IGNORECASE,
)

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


def _surface_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Word-boundary patterns for every surface form of every canonical term (longest first)."""
    forms: dict[str, str] = {}
    for term in compatibility_vocabulary.TERMS:
        for form in compatibility_vocabulary.surface_forms(term.canonical):
            if len(form) >= 3:  # "lan", "hue" and longer; shorter forms are too ambiguous in prose
                forms.setdefault(form, term.canonical)
    ordered = sorted(forms, key=len, reverse=True)
    return [(re.compile(rf"(?<![\w-]){re.escape(form)}(?![\w-])", re.IGNORECASE), forms[form]) for form in ordered]


_TERM_PATTERNS = _surface_patterns()
# Terms whose everyday meaning collides with prose ("no matter what", "Funk" in German compounds).
_AMBIGUOUS_WORDS = frozenset({"matter", "funk", "lan", "hue", "nest"})


def _terms_in(sentence: str) -> set[str]:
    found: set[str] = set()
    for pattern, canonical in _TERM_PATTERNS:
        for match in pattern.finditer(sentence):
            word = match.group(0)
            if word.casefold() in _AMBIGUOUS_WORDS and not word[0].isupper():
                continue  # lowercase "matter"/"hue" in running text is not the product term
            found.add(canonical)
    return found


def _walk(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _walk(child)


def _tool_products(tool_responses: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """id -> title of every product that appeared in this turn's tool results."""
    products: dict[str, str] = {}
    for node in _walk(list(tool_responses)):
        pid = node.get("id") or node.get("product_id")
        if isinstance(pid, str) and isinstance(node.get("title"), str):
            products[pid] = node["title"]
        elif isinstance(pid, str):
            products.setdefault(pid, "")
    return products


class OutputValidator:
    def __init__(
        self,
        catalog: CatalogReader,
        guardrail: SemanticGuardrail | None = None,
        leak_markers: Sequence[str] = (),
        min_domain_check_chars: int = 200,
    ) -> None:
        self._catalog = catalog
        self._guardrail = guardrail
        self._leak_markers = [m for m in leak_markers if m.strip()]
        self._min_domain_check_chars = min_domain_check_chars

    def validate(
        self,
        text: str,
        tool_responses: Sequence[Mapping[str, Any]] = (),
        session_product_ids: Sequence[str] = (),
    ) -> list[Violation]:
        """`session_product_ids`: products discussed earlier (session state), so a claim in a turn without
        tool calls ("does the first one work with Alexa?" -> "yes, it does") is still checked."""
        sentences = [s.strip() for s in _SENTENCES.split(text) if s.strip()]
        violations = [
            *self._electrical(sentences),
            *self._prompt_leak(text),
        ]
        tool_products = _tool_products(tool_responses)
        try:
            violations += self._products(text, tool_products)
            violations += self._compatibility(sentences, tool_products, session_product_ids)
        except Exception:  # the catalog being down must not turn every answer into a fallback
            logger.warning("output check: catalog lookup failed, product checks skipped", exc_info=True)
        if not violations and not tool_responses:
            violations += self._off_topic(text)
        return violations

    @staticmethod
    def _electrical(sentences: Sequence[str]) -> list[Violation]:
        return [
            Violation(kind="electrical", detail=sentence[:160])
            for sentence in sentences
            if _INSTRUCTION.search(sentence) and _WIRE_TERMS.search(sentence) and not _REFUSAL.search(sentence)
        ]

    def _prompt_leak(self, text: str) -> list[Violation]:
        folded = text.casefold()
        return [
            Violation(kind="prompt_leak", detail=marker[:80])
            for marker in self._leak_markers
            if marker.casefold() in folded
        ]

    def _products(self, text: str, tool_products: Mapping[str, str]) -> list[Violation]:
        mentioned = [pid for pid in dict.fromkeys(_PRODUCT_ID.findall(text)) if pid not in tool_products]
        if not mentioned:
            return []
        known = {p.id for p in self._catalog.get_products(mentioned)}
        return [Violation(kind="unknown_product", detail=pid) for pid in mentioned if pid not in known]

    def _compatibility(
        self, sentences: Sequence[str], tool_products: Mapping[str, str], session_product_ids: Sequence[str]
    ) -> list[Violation]:
        candidates = [
            (s, terms) for s in sentences if _CLAIM.search(s) and not _HEDGE.search(s) if (terms := _terms_in(s))
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

    def _off_topic(self, text: str) -> list[Violation]:
        if self._guardrail is None or len(text) < self._min_domain_check_chars:
            return []
        try:
            decision = self._guardrail.classify(text)
        except Exception:
            logger.warning("output check: domain embedding failed, check skipped", exc_info=True)
            return []
        if decision.category is Category.OFF_TOPIC:
            return [Violation(kind="off_topic", detail=f"score={decision.score}")]
        return []
