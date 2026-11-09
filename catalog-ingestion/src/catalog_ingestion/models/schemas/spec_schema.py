from pydantic import BaseModel, Field


class SpecSchema(BaseModel):
    name: str = Field(description="Specification name in English, e.g. 'Battery life'.")
    value: str = Field(description="Value exactly as stated in the source, e.g. '5 Jahre' or '868,3 MHz'.")
    unit: str | None = Field(default=None, description="Unit if separable, e.g. 'MHz'.")
