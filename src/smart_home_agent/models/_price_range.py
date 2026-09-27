from typing import Self

from pydantic import BaseModel, Field, model_validator


class PriceRangeModel(BaseModel):
    """Base for requests with an optional price range: `min_price` must not exceed `max_price`."""

    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _price_range(self) -> Self:
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must not be greater than max_price")
        return self
