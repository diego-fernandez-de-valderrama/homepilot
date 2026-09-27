from smart_home_agent.models.product import ProductVersion
from smart_home_agent.models.recommendation.types import VersionStatus


class VersionOption(ProductVersion):
    """Another version of a recommended product, with its own result for this request."""

    status: VersionStatus
    filter_reason: str | None = None  # the hard filter that removed it (price, brand, ...) when filtered_out
