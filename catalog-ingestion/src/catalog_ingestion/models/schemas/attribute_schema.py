from pydantic import BaseModel


class AttributeSchema(BaseModel):
    section: str
    key: str
    value: str
