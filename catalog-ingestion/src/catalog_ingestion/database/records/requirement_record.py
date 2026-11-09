from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from catalog_ingestion.database.records._enum_check import EnumCheck
from catalog_ingestion.database.records.base import Base
from catalog_ingestion.vocabulary import FactSource, Method, Necessity, RequirementKind


class RequirementRecord(Base):
    __tablename__ = "product_requirements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    item: Mapped[str]
    canonical_item: Mapped[str | None]
    kind: Mapped[str]
    necessity: Mapped[str]  # required | required_for_some_features
    alternatives: Mapped[list[str]]  # any one alternative satisfies the requirement
    source: Mapped[str]
    source_field: Mapped[str | None]
    source_url: Mapped[str | None]
    evidence: Mapped[str]
    confidence: Mapped[float]
    method: Mapped[str]

    __table_args__ = (
        EnumCheck.one_of("kind", RequirementKind),
        EnumCheck.one_of("necessity", Necessity),
        EnumCheck.one_of("source", FactSource),
        EnumCheck.one_of("method", Method),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        Index("product_requirements_product_idx", "product_id"),
        Index("product_requirements_item_idx", "canonical_item"),
    )
