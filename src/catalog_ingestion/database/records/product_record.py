from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Index, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog_ingestion.database.records._enum_check import EnumCheck
from catalog_ingestion.database.records.base import Base
from catalog_ingestion.vocabulary import CompletenessLevel, WebStatus

if TYPE_CHECKING:
    from catalog_ingestion.database.records.compatibility_record import CompatibilityRecord
    from catalog_ingestion.database.records.requirement_record import RequirementRecord


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(primary_key=True)  # original dataset id (stable key)
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    title: Mapped[str]
    brand: Mapped[str | None]
    category: Mapped[str | None]
    category_slug: Mapped[str | None]
    product_type: Mapped[str | None]
    is_smart_home: Mapped[bool | None]
    price_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_currency: Mapped[str | None]
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ean: Mapped[str | None]
    image_url: Mapped[str | None]
    source_url: Mapped[str | None]
    summary_en: Mapped[str | None]
    summary_de: Mapped[str | None]
    completeness_level: Mapped[str]
    completeness_score: Mapped[float]
    web_status: Mapped[str]
    raw: Mapped[dict[str, Any]]  # original JSON, untouched
    document: Mapped[dict[str, Any]]  # CatalogProductSchema (enriched + normalized)
    attributes: Mapped[dict[str, Any]]  # {section: {key: value}} for ad-hoc queries
    llm_output: Mapped[dict[str, Any] | None]  # cached raw LLM output (before validation)
    raw_hash: Mapped[str]
    document_hash: Mapped[str]
    enrichment_hash: Mapped[str | None]
    enrichment_model: Mapped[str | None]
    prompt_version: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    compatibility: Mapped[list["CompatibilityRecord"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="CompatibilityRecord.id"
    )
    requirements: Mapped[list["RequirementRecord"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="RequirementRecord.id"
    )

    __table_args__ = (
        EnumCheck.one_of("completeness_level", CompletenessLevel),
        EnumCheck.one_of("web_status", WebStatus),
        Index("products_category_idx", "category", postgresql_where=text("active")),
        Index("products_brand_idx", "brand", postgresql_where=text("active")),
        Index("products_price_idx", "price_value", postgresql_where=text("active")),
    )
