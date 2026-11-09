from pydantic import BaseModel


class PriceSchema(BaseModel):
    value: float | None
    currency: str | None
    original_value: float | None = None
    savings: float | None = None
    raw: str = ""
