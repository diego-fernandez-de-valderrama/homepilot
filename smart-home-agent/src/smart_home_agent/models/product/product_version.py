from pydantic import BaseModel


class ProductVersion(BaseModel):
    """Another version of a product (same title): enough to name it and to offer it by id."""

    id: str
    variant: str | None
    subtitle: str | None
    price: float | None
    currency: str | None
