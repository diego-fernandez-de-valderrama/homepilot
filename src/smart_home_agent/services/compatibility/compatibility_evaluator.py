from collections.abc import Sequence

from catalog_ingestion.vocabulary import FactStatus, Necessity, RequirementKind

from smart_home_agent.models import (
    CompatibilityResult,
    Product,
    ProductRequirement,
    RequirementCheck,
    RequirementStatus,
    TermCheck,
)
from smart_home_agent.services.compatibility._notes import related_notes, unmapped_mentions
from smart_home_agent.services.vocabulary import ResolvedTerm, Vocabulary

_DEVICE_KINDS = (RequirementKind.HUB, RequirementKind.GATEWAY)


class CompatibilityEvaluator:
    """Pure decisions on one product's stored facts (no catalog access). `evaluate` is the entry point."""

    @classmethod
    def evaluate(
        cls, product: Product, terms: Sequence[ResolvedTerm], owned_devices: Sequence[str] | None = None
    ) -> CompatibilityResult:
        checks = [cls.check_term(product, t) for t in terms]
        return CompatibilityResult(
            product_id=product.id,
            title=product.title,
            overall=cls.overall_status(checks),
            checks=checks,
            requirements=[cls.check_requirement(r, owned_devices) for r in product.requirements],
            requires_professional_installation=product.requires_professional_installation,
            uses_owned_hub=cls.uses_owned_hub(product, owned_devices),
        )

    @staticmethod
    def term_status(product: Product, canonical: str) -> tuple[FactStatus, list[str]]:
        """Status of one canonical value for one product, plus explanatory notes."""
        facts = product.facts_for(canonical)
        statuses = {fact.status for fact in facts}
        if FactStatus.SUPPORTED in statuses and FactStatus.UNSUPPORTED in statuses:
            return FactStatus.UNKNOWN, ["The catalog contains contradicting evidence for this value."]
        if FactStatus.SUPPORTED in statuses:
            return FactStatus.SUPPORTED, []
        if FactStatus.UNSUPPORTED in statuses:
            return FactStatus.UNSUPPORTED, []
        return FactStatus.UNKNOWN, ["The catalog has no information about this value."]

    @classmethod
    def check_term(cls, product: Product, resolved: ResolvedTerm) -> TermCheck:
        status, notes = cls.term_status(product, resolved.canonical)
        if status is FactStatus.UNKNOWN:
            notes = notes + related_notes(product, resolved) + unmapped_mentions(product, resolved)
        return TermCheck(
            term=resolved.canonical,
            label=resolved.label,
            dimension=resolved.dimension,
            status=status,
            evidence=[fact.evidence for fact in product.facts_for(resolved.canonical)],
            notes=notes,
        )

    @staticmethod
    def check_requirement(requirement: ProductRequirement, owned_devices: Sequence[str] | None) -> RequirementCheck:
        status: RequirementStatus = "info"
        if requirement.kind in _DEVICE_KINDS and requirement.necessity is Necessity.REQUIRED:
            options = set(requirement.alternatives) | (
                {requirement.canonical_item} if requirement.canonical_item else set()
            )
            if "standalone" in options or (owned_devices and options & set(owned_devices)):
                status = "satisfied"
            elif owned_devices is None:
                status = "unverified"
            else:
                status = "missing"
        return RequirementCheck(
            label=requirement.label,
            canonical_item=requirement.canonical_item,
            kind=requirement.kind,
            necessity=requirement.necessity,
            alternatives=[Vocabulary.requirement_label(a) for a in requirement.alternatives],
            status=status,
            evidence=requirement.evidence,
        )

    @staticmethod
    def uses_owned_hub(product: Product, owned_devices: Sequence[str] | None) -> bool:
        """A hub/gateway requirement of the product (for all or some features) names a device the customer owns."""
        owned = set(owned_devices or ())
        return any(
            r.kind in _DEVICE_KINDS
            and owned & ({*r.alternatives} | ({r.canonical_item} if r.canonical_item else set()))
            for r in product.requirements
        )

    @staticmethod
    def overall_status(checks: Sequence[TermCheck]) -> FactStatus:
        statuses = {check.status for check in checks}
        if FactStatus.UNSUPPORTED in statuses:
            return FactStatus.UNSUPPORTED
        if statuses <= {FactStatus.SUPPORTED}:
            return FactStatus.SUPPORTED
        return FactStatus.UNKNOWN
