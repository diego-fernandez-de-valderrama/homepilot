from pydantic import BaseModel, Field

from smart_home_agent.models.cart.types import MAX_QUANTITY


class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=MAX_QUANTITY)
