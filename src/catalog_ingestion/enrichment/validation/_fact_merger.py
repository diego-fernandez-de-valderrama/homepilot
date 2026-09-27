from catalog_ingestion.models import CompatibilityFact, Requirement


class FactMerger:
    """Merges accepted LLM facts into the deterministic ones. Deterministic catalog facts win."""

    @staticmethod
    def merge_facts(
        deterministic: tuple[CompatibilityFact, ...], llm_facts: list[CompatibilityFact]
    ) -> tuple[tuple[CompatibilityFact, ...], list[str]]:
        """Conflicting LLM facts are dropped and reported."""
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

    @staticmethod
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
