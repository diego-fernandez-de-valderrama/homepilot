from pydantic import BaseModel


class SpecOutSchema(BaseModel):
    name: str
    value: str
    unit: str | None = None
