from catalog_ingestion.domain.enums import FactStatus
from pydantic import BaseModel, Field

from smart_home_agent.models.compatibility.accessory_suggestion import AccessorySuggestion
from smart_home_agent.models.compatibility.requirement_check import RequirementCheck
from smart_home_agent.models.compatibility.term_check import TermCheck


class CompatibilityResult(BaseModel):
    product_id: str
    title: str
    overall: FactStatus
    checks: list[TermCheck]
    requirements: list[RequirementCheck]
    requires_professional_installation: bool
    accessories: list[AccessorySuggestion] = Field(default_factory=list)  # catalog hubs for missing/unverified hubs
    # The catalog names a hub/gateway for this product that the customer said they own (a ranking signal only).
    uses_owned_hub: bool = Field(default=False, exclude=True)

    def needed_hubs(self) -> frozenset[str]:
        """Required hubs/gateways the customer does not (or did not say they) own."""
        return frozenset(
            r.canonical_item or r.label for r in self.requirements if r.status in ("missing", "unverified")
        )
