"""Validation: deterministic facts + (optional) LLM output -> a validated `EnrichedProduct`. The catalog wins.

`Validator.validate` checks every LLM claim against the texts the model saw (private `_source_texts`):

1. `_compatibility_claim_check` / `_requirement_claim_check`: the evidence quote must be found in a source
   (`_quote_matcher`), name the claimed term as whole words, and not negate it in its own clause
   (`_mention_matcher`; `unsupported` needs a negation earlier in the clause); requirement alternatives
   must be named in the evidence sentence. Confidence and evidence are assigned by rule (`_claim_provenance`).
2. `_fact_merger`: deterministic facts win; conflicting LLM facts are dropped and reported.
3. Category, brand and specs (`_spec_check`) are kept only when the sources support them.

Everything dropped is recorded in `validation_notes`.
"""

from catalog_ingestion.enrichment.validation.validator import Validator

__all__ = ["Validator"]
