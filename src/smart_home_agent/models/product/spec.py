from pydantic import BaseModel


class Spec(BaseModel):
    name: str
    value: str
    unit: str | None = None
