"""Input boundary: one product JSON file from products.zip."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RawProductSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    title: str
    subtitle: str = ""
    price: str = ""
    variants: list[str] = Field(default_factory=list)
    description: str = ""
    attributes: str = ""
    image: str = ""
    url: str = ""

    @field_validator("id", mode="before")
    @classmethod
    def _id_as_string(cls, value: Any) -> Any:
        return str(value) if isinstance(value, int) else value

    @field_validator("subtitle", "price", "description", "attributes", "image", "url", mode="before")
    @classmethod
    def _none_as_empty(cls, value: Any) -> Any:
        return "" if value is None else value

    @field_validator("variants", mode="before")
    @classmethod
    def _variants_as_list(cls, value: Any) -> Any:
        return [] if value is None else value
