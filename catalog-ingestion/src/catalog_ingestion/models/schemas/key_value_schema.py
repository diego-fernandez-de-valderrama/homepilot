from pydantic import BaseModel


class KeyValueSchema(BaseModel):
    key: str
    value: str
