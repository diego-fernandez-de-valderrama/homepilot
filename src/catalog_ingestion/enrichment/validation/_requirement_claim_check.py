import re

from catalog_ingestion.enrichment.validation._claim_provenance import ClaimProvenance
from catalog_ingestion.enrichment.validation._mention_matcher import MentionMatcher
from catalog_ingestion.enrichment.validation._outcome import Outcome
from catalog_ingestion.enrichment.validation._quote_matcher import QuoteMatcher
from catalog_ingestion.enrichment.validation._source_texts import SourceTexts
from catalog_ingestion.enrichment.validation._text_normalizer import TextNormalizer
from catalog_ingestion.models import Requirement, RequirementClaim
from catalog_ingestion.vocabulary import Method, RequirementVocabulary


class RequirementClaimCheck:
    """An LLM requirement claim -> a requirement: evidence check, negation, and only the alternatives the
    evidence sentence names."""

    _WORD = re.compile(r"[\wäöüß+-]{4,}", re.IGNORECASE)

    @staticmethod
    def check(claim: RequirementClaim, sources: SourceTexts) -> Outcome[Requirement]:
        label = f"requirement '{claim.item}'"
        source = sources.locate(claim.evidence_quote, claim.source)
        if source is None:
            return Outcome(None, f"dropped {label}: evidence quote not found in sources")

        term = RequirementVocabulary.lookup(claim.item)
        if term is not None:
            if not term.pattern.search(claim.evidence_quote):
                return Outcome(None, f"dropped {label}: evidence does not mention {term.label}")
        else:
            words = {word.casefold() for word in RequirementClaimCheck._WORD.findall(claim.item)}
            if words and not any(word in TextNormalizer.normalize(claim.evidence_quote) for word in words):
                return Outcome(None, f"dropped {label}: evidence does not mention the item")

        mention = term.pattern if term is not None else MentionMatcher.words_pattern(claim.item)
        lines = sources.lines_for(source)
        if mention is not None and MentionMatcher.negated(mention, claim.evidence_quote, lines):
            return Outcome(None, f"dropped {label}: the evidence negates it")

        sentence = QuoteMatcher.sentence(claim.evidence_quote, lines) or ""
        context = f"{TextNormalizer.normalize(claim.evidence_quote)}\n{sentence}"
        verified = [alt for alt in claim.alternatives if alt.strip() and RequirementClaimCheck._mentioned(alt, context)]
        dropped = [alt for alt in claim.alternatives if alt.strip() and alt not in verified]
        primary = term.canonical if term else None
        alternatives = tuple(
            dict.fromkeys([primary or claim.item.strip(), *map(RequirementClaimCheck._canonical_or_raw, verified)])
        )
        return Outcome(
            Requirement(
                item=claim.item,
                canonical_item=primary,
                kind=term.kind if term else claim.kind,
                necessity=claim.necessity,
                alternatives=alternatives,
                evidence=ClaimProvenance.evidence(source, claim.evidence_quote, sources),
                confidence=ClaimProvenance.confidence(source, sources),
                method=Method.LLM,
            ),
            f"dropped alternatives of {label} not named in the evidence: {', '.join(dropped)}" if dropped else None,
        )

    @staticmethod
    def _canonical_or_raw(item: str) -> str:
        term = RequirementVocabulary.lookup(item)
        return term.canonical if term else item.strip()

    @staticmethod
    def _mentioned(item: str, normalized_context: str) -> bool:
        """An alternative is kept only when the evidence sentence names it (its vocabulary pattern or its words)."""
        term = RequirementVocabulary.term_by_canonical(item.strip()) or RequirementVocabulary.lookup(item)
        if term is not None:
            return bool(term.pattern.search(normalized_context))
        words = {word.casefold() for word in RequirementClaimCheck._WORD.findall(item)}
        return bool(words) and all(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", normalized_context) for word in words)
