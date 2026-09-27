from pydantic import BaseModel


class CartChange(BaseModel):
    """One product of an add/remove call: units to add or remove (None for remove: all units)."""

    product_id: str
    quantity: int | None
