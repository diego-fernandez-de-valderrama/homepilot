from pydantic import BaseModel

from catalog_ingestion.vocabulary import WebStatus


class WebInfoSchema(BaseModel):
    status: WebStatus
    url: str | None = None
    method: str | None = None
