from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from catalog_ingestion.database.records.base import Base


class RetrievalDocumentRecord(Base):
    __tablename__ = "retrieval_documents"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    text: Mapped[str]
    doc_hash: Mapped[str]
    indexed_doc_hash: Mapped[str | None]
    embedding_model: Mapped[str | None]
    indexed_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
