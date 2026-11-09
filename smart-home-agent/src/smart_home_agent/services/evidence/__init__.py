"""Provenance lookup: where a product fact or field value comes from. Only stored evidence is returned.

EvidenceService(catalog).get(product_id, topic)   # reads the product
EvidenceLookup.for_product(product, topic)        # pure lookup; `EvidenceLookup.TOPICS_HELP` for the tool
"""

from smart_home_agent.services.evidence.evidence_lookup import EvidenceLookup
from smart_home_agent.services.evidence.evidence_service import EvidenceService

__all__ = ["EvidenceLookup", "EvidenceService"]
