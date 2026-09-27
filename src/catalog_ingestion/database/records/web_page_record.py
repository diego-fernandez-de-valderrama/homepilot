from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from catalog_ingestion.database.records.base import Base


class WebPageRecord(Base):
    __tablename__ = "web_pages"

    url: Mapped[str] = mapped_column(primary_key=True)
    product_id: Mapped[str]
    ok: Mapped[bool]
    method: Mapped[str | None]
    http_status: Mapped[int | None]
    text: Mapped[str]
    error: Mapped[str | None]
    fetched_at: Mapped[datetime]
