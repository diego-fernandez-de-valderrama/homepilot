from typing import Literal

from pydantic import BaseModel


class AccessorySuggestion(BaseModel):
    """A catalog hub/gateway that a product requires and the customer may not own yet."""

    for_product_id: str
    requirement_label: str
    canonical_item: str
    status: Literal["missing", "unverified"]  # missing = user said they do not own it; unverified = not stated
    product_id: str
    title: str
    price: float
    bundle_total: float  # price of `for_product_id` + this accessory
