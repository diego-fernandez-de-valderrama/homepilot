"""Hub/gateway cross-sell: the catalog product that satisfies a required hub the customer may not own yet.

A product whose hub requirement is `missing` (the customer said they do not own it) or `unverified` (ownership
not stated) is only usable with that hub, so offering the hub is a factual, data-backed basket addition.
The mapping is keyed by the canonical requirement ids of `RequirementVocabulary` (`catalog_ingestion.vocabulary`) and
matches plain hub products in the `hub_gateway` category by title keywords (starter sets are never offered).
Requirements without a safe mapping (generic `smart_hub`, partner solutions) get no suggestion.
"""

from smart_home_agent.services.accessories.accessory_service import AccessoryService

__all__ = ["AccessoryService"]
