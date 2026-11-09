from pydantic import BaseModel, Field


class UpsellSuggestion(BaseModel):
    product_id: str
    title: str
    variant: str | None = None  # the upsell's version label (color, size, pack), when it has one
    price: float
    base_product_id: str
    price_difference: float
    upgrade_reasons: list[str]  # factual, computed from structured data
    # The same advantages as data, for the KPI eval (never sent to the model): capability ids the best match lacks,
    # and whether the upsell works without a hub the best match needs.
    extra_capabilities: list[str] = Field(default_factory=list, exclude=True)
    replaces_hub: bool = Field(default=False, exclude=True)
