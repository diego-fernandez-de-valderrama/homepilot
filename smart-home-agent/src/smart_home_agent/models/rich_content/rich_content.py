from pydantic import BaseModel, Field

from smart_home_agent.models.comparison import ComparisonResult
from smart_home_agent.models.product import Product
from smart_home_agent.models.recommendation import UpsellSuggestion
from smart_home_agent.models.rich_content.product_compatibility import ProductCompatibility


class RichContent(BaseModel):
    """Catalog data for the tags of one answer, keyed like the tags (never taken from the model's text)."""

    products: dict[str, Product] = Field(default_factory=dict)
    compatibility: dict[str, ProductCompatibility] = Field(default_factory=dict)
    comparisons: dict[str, ComparisonResult] = Field(default_factory=dict)  # compare_key(ids) -> result
    upgrades: dict[str, UpsellSuggestion] = Field(default_factory=dict)  # upgrade_key(from, to) -> upsell

    @staticmethod
    def compare_key(ids: tuple[str, ...]) -> str:
        return ",".join(ids)

    @staticmethod
    def upgrade_key(from_id: str, to_id: str) -> str:
        return f"{from_id}>{to_id}"

    def titles(self) -> dict[str, str]:
        return {pid: p.title for pid, p in self.products.items()}

    def names(self) -> dict[str, str]:
        """Display names: the title plus the version label, so two versions of one product read differently."""
        return {pid: p.name for pid, p in self.products.items()}
