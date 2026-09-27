from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, func, text
from sqlalchemy.orm import Mapped, mapped_column

from catalog_ingestion.database.records.base import Base


class IngestionRunRecord(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(server_default=text("'running'"))
    args: Mapped[dict[str, Any]]
    stats: Mapped[dict[str, Any] | None]
