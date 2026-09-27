"""Turns unvalidated LLM claims into facts: evidence check, canonicalization, precedence."""

import re
from dataclasses import dataclass

from catalog_ingestion.domain.enrichment import CompatibilityClaim, RequirementClaim
from catalog_ingestion.domain.enums import FactSource, FactStatus, Method
from catalog_ingestion.domain.facts import CompatibilityFact, Evidence, Requirement
from catalog_ingestion.validation.evidence import (
    SourceTexts,
    mentions_any,
    negation_near,
    normalize_text,
    quote_sentence,
)
from catalog_ingestion.vocabulary import compatibility as compat_vocab
from catalog_ingestion.vocabulary import requirements as req_vocab

# Confidence is assigned by rule, never taken from the model.
CONFIDENCE_LLM_FROM_CATALOG = 0.9
CONFIDENCE_LLM_FROM_WEB = 0.8
# Page text read through Gemini url_context is itself model output, not a verbatim page copy.
CONFIDENCE_LLM_FROM_GENERATED_WEB = 0.6
CONFIDENCE_LLM_DERIVED = 0.6
GENERATED_WEB_METHOD = "gemini_url_context"

_WORD = re.compile(r"[\wäöüß+-]{4,}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Outcome[T]:
    value: T | None
    note: str | None = None


def _confidence(source: FactSource, sources: SourceTexts) -> float:
    if source is not FactSource.WEB:
        return CONFIDENCE_LLM_FROM_CATALOG
    return CONFIDENCE_LLM_FROM_GENERATED_WEB if sources.web_method == GENERATED_WEB_METHOD else CONFIDENCE_LLM_FROM_WEB


def _evidence(source: FactSource, quote: str, sources: SourceTexts) -> Evidence:
    if source is FactSource.WEB:
        field = "web_page:url_context" if sources.web_method == GENERATED_WEB_METHOD else "web_page"
        return Evidence(FactSource.WEB, quote, field=field, url=sources.web_url)
    return Evidence(FactSource.CATALOG, quote, field="catalog_text")


def compatibility_from_claim(claim: CompatibilityClaim, sources: SourceTexts) -> Outcome[CompatibilityFact]:
    label = f"{claim.dimension.value} '{claim.value}'"
    source = sources.locate(claim.evidence_quote, claim.source)
    if source is None:
        return Outcome(None, f"dropped {label}: evidence quote not found in sources")

    term = compat_vocab.lookup(claim.value)
    if term is not None:
        if not mentions_any(claim.evidence_quote, compat_vocab.surface_forms(term.canonical)):
            return Outcome(None, f"dropped {label}: evidence does not mention {term.label}")
        dimension, canonical = term.dimension, term.canonical
    else:
        if normalize_text(claim.value) not in normalize_text(claim.evidence_quote):
            return Outcome(None, f"dropped {label}: evidence does not mention the value")
        dimension, canonical = claim.dimension, None

    negated = negation_near(claim.evidence_quote, sources.text_for(source))
    if claim.status is FactStatus.SUPPORTED and negated:
        return Outcome(None, f"dropped {label}: the evidence negates it")
    if claim.status is FactStatus.UNSUPPORTED and not negated:
        return Outcome(None, f"dropped {label}: 'unsupported' needs explicit negative evidence")

    note = None
    if dimension is not claim.dimension:
        note = f"reassigned {label} to dimension {dimension.value}"
    return Outcome(
        CompatibilityFact(
            dimension=dimension,
            raw_value=claim.value,
            canonical_value=canonical,
            status=claim.status,
            evidence=_evidence(source, claim.evidence_quote, sources),
            confidence=_confidence(source, sources),
            method=Method.LLM,
        ),
        note,
    )


def _canonical_or_raw(item: str) -> str:
    term = req_vocab.lookup(item)
    return term.canonical if term else item.strip()


def requirement_from_claim(claim: RequirementClaim, sources: SourceTexts) -> Outcome[Requirement]:
    label = f"requirement '{claim.item}'"
    source = sources.locate(claim.evidence_quote, claim.source)
    if source is None:
        return Outcome(None, f"dropped {label}: evidence quote not found in sources")

    term = req_vocab.lookup(claim.item)
    if term is not None:
        if not term.pattern.search(claim.evidence_quote):
            return Outcome(None, f"dropped {label}: evidence does not mention {term.label}")
    else:
        words = {word.casefold() for word in _WORD.findall(claim.item)}
        if words and not any(word in normalize_text(claim.evidence_quote) for word in words):
            return Outcome(None, f"dropped {label}: evidence does not mention the item")

    if negation_near(claim.evidence_quote, sources.text_for(source)):
        return Outcome(None, f"dropped {label}: the evidence negates it")

    sentence = quote_sentence(claim.evidence_quote, sources.text_for(source)) or ""
    context = f"{normalize_text(claim.evidence_quote)}\n{sentence}"
    verified = [alt for alt in claim.alternatives if alt.strip() and _mentioned(alt, context)]
    dropped = [alt for alt in claim.alternatives if alt.strip() and alt not in verified]
    primary = term.canonical if term else None
    alternatives = tuple(dict.fromkeys([primary or claim.item.strip(), *map(_canonical_or_raw, verified)]))
    return Outcome(
        Requirement(
            item=claim.item,
            canonical_item=primary,
            kind=term.kind if term else claim.kind,
            necessity=claim.necessity,
            alternatives=alternatives,
            evidence=_evidence(source, claim.evidence_quote, sources),
            confidence=_confidence(source, sources),
            method=Method.LLM,
        ),
        f"dropped alternatives of {label} not named in the evidence: {', '.join(dropped)}" if dropped else None,
    )


def _mentioned(item: str, normalized_context: str) -> bool:
    """An alternative is kept only when the evidence sentence names it (its vocabulary pattern or its words)."""
    term = req_vocab.term_by_canonical(item.strip()) or req_vocab.lookup(item)
    if term is not None:
        return bool(term.pattern.search(normalized_context))
    words = {word.casefold() for word in _WORD.findall(item)}
    return bool(words) and all(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", normalized_context) for word in words)


def merge_facts(
    deterministic: tuple[CompatibilityFact, ...], llm_facts: list[CompatibilityFact]
) -> tuple[tuple[CompatibilityFact, ...], list[str]]:
    """Deterministic catalog facts win. Conflicting LLM facts are dropped and reported."""
    merged = list(deterministic)
    by_key = {fact.key: fact for fact in deterministic}
    notes: list[str] = []
    for fact in llm_facts:
        existing = by_key.get(fact.key)
        if existing is None:
            by_key[fact.key] = fact
            merged.append(fact)
        elif existing.status is not fact.status:
            notes.append(
                f"conflict on {fact.dimension.value} '{fact.raw_value}': kept {existing.status.value} "
                f"({existing.evidence.source.value}), dropped {fact.status.value} ({fact.evidence.source.value})"
            )
    return tuple(merged), notes


def merge_requirements(
    deterministic: tuple[Requirement, ...], llm_requirements: list[Requirement]
) -> tuple[Requirement, ...]:
    merged = list(deterministic)
    seen = {requirement.key for requirement in deterministic}
    for requirement in llm_requirements:
        if requirement.key not in seen:
            seen.add(requirement.key)
            merged.append(requirement)
    return tuple(merged)
