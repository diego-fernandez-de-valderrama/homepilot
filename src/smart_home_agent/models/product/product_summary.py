from pydantic import BaseModel, Field


class ProductSummary(BaseModel):
    """Compact view used in lists (search, filter, recommendation)."""

    id: str
    title: str
    brand: str | None
    category: str | None
    category_label_en: str | None
    category_label_de: str | None
    product_type: str | None
    price: float | None
    currency: str | None
    original_price: float | None
    summary_en: str | None
    summary_de: str | None
    source_url: str | None
    # Versions of one product (color, size, pack) share a title; these catalog strings tell them apart.
    subtitle: str | None = None
    variant: str | None = None  # this version's own option label, e.g. "Anthrazit", "2 Stk.", "806 lm"
    variant_options: list[str] = Field(default_factory=list)  # every option label the shop lists for the product

    @property
    def name(self) -> str:
        """Title plus this version's option label when it has one ("Access Point 2 (Anthrazit)")."""
        return f"{self.title} ({self.variant})" if self.variant else self.title
