from catalog_ingestion.enrichment.validation._claim_provenance import ClaimProvenance
from catalog_ingestion.enrichment.validation._mention_matcher import MentionMatcher
from catalog_ingestion.enrichment.validation._outcome import Outcome
from catalog_ingestion.enrichment.validation._source_texts import SourceTexts
from catalog_ingestion.enrichment.validation._text_normalizer import TextNormalizer
from catalog_ingestion.models import CompatibilityClaim, CompatibilityFact
from catalog_ingestion.vocabulary import CompatibilityVocabulary, FactStatus, Method


class CompatibilityClaimCheck:
    """An LLM compatibility claim -> a fact: evidence check, canonicalization, negation rules."""

    @staticmethod
    def check(claim: CompatibilityClaim, sources: SourceTexts) -> Outcome[CompatibilityFact]:
        label = f"{claim.dimension.value} '{claim.value}'"
        source = sources.locate(claim.evidence_quote, claim.source)
        if source is None:
            return Outcome(None, f"dropped {label}: evidence quote not found in sources")

        term = CompatibilityVocabulary.lookup(claim.value)
        if term is not None:
            forms = CompatibilityVocabulary.surface_forms(term.canonical)
            if not MentionMatcher.mentions_any(claim.evidence_quote, forms):
                return Outcome(None, f"dropped {label}: evidence does not mention {term.label}")
            mention = MentionMatcher.forms_pattern(forms)
            dimension, canonical = term.dimension, term.canonical
        else:
            if TextNormalizer.normalize(claim.value) not in TextNormalizer.normalize(claim.evidence_quote):
                return Outcome(None, f"dropped {label}: evidence does not mention the value")
            # By its words: a value such as "Stick Up Cam (1. Generation)" spans several clauses.
            mention = MentionMatcher.words_pattern(claim.value) or MentionMatcher.forms_pattern((claim.value,))
            dimension, canonical = claim.dimension, None

        lines = sources.lines_for(source)
        if claim.status is FactStatus.SUPPORTED and MentionMatcher.negated(mention, claim.evidence_quote, lines):
            return Outcome(None, f"dropped {label}: the evidence negates it")
        if claim.status is FactStatus.UNSUPPORTED and not MentionMatcher.negated(
            mention, claim.evidence_quote, lines, max_words_before=None
        ):
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
                evidence=ClaimProvenance.evidence(source, claim.evidence_quote, sources),
                confidence=ClaimProvenance.confidence(source, sources),
                method=Method.LLM,
            ),
            note,
        )
