from pydantic import BaseModel


class CentralUnitsAsked(BaseModel):
    """Several units of central units (hubs, controllers, starter sets) that add_to_cart refused, so the model asks
    the customer. The same add is allowed in a later turn (another invocation), after the customer answered."""

    invocation_id: str
    units: dict[str, int]  # product id -> units the cart would hold
