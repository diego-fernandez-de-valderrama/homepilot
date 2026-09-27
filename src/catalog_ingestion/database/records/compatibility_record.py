from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from catalog_ingestion.database.records._enum_check import EnumCheck
from catalog_ingestion.database.records.base import Base
from catalog_ingestion.vocabulary import Dimension, FactSource, FactStatus, Method


class CompatibilityRecord(Base):
    __tablename__ = "product_compatibility"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    dimension: Mapped[str]  # ecosystem | voice_assistant | protocol | mobile_os | control
    canonical_value: Mapped[str | None]  # NULL when the raw value has no safe canonical mapping
    label: Mapped[str | None]
    raw_value: Mapped[str]
    status: Mapped[str]  # supported | unsupported | unknown
    source: Mapped[str]  # catalog | web | llm
    source_field: Mapped[str | None]
    source_url: Mapped[str | None]
    evidence: Mapped[str]
    confidence: Mapped[float]
    method: Mapped[str]  # deterministic | llm

    __table_args__ = (
        EnumCheck.one_of("dimension", Dimension),
        EnumCheck.one_of("status", FactStatus),
        EnumCheck.one_of("source", FactSource),
        EnumCheck.one_of("method", Method),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        Index("product_compatibility_lookup_idx", "dimension", "canonical_value", "status"),
        Index("product_compatibility_product_idx", "product_id"),
    )
