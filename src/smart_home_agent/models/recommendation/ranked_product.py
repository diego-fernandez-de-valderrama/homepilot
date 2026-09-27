from catalog_ingestion.vocabulary import FactStatus
from pydantic import BaseModel, Field

from smart_home_agent.models.compatibility import TermCheck
from smart_home_agent.models.product import ProductSummary
from smart_home_agent.models.recommendation.version_option import VersionOption


class RankedProduct(BaseModel):
    product: ProductSummary
    compatibility: FactStatus  # overall status for the requested terms
    checks: list[TermCheck]
    relevance: float
    score: float
    capabilities: list[str]  # labels of confirmed ecosystems, voice assistants and protocols
    missing_requirements: list[str]  # required hubs/gateways the user said they do not own
    unverified_requirements: list[str]  # required hubs/gateways; ownership not stated
    requires_professional_installation: bool
    other_versions: list[VersionOption] = Field(default_factory=list)  # same title, other color/size/pack
