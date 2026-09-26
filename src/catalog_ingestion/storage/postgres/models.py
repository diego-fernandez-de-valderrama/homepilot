"""SQLAlchemy ORM models: the PostgreSQL schema.

These are persistence models only. The pipeline works on frozen dataclasses
(`catalog_ingestion.domain`); the repository converts between the two.

Hybrid model:
  * typed columns + child tables for everything the agent filters or joins on
    deterministically (price, category, brand, compatibility, requirements);
  * JSONB for heterogeneous data (302 distinct attribute keys), the full enriched
    document and audit copies (raw input, cached LLM output).

Schema changes go through Alembic: edit these models, then
`uv run alembic revision --autogenerate -m "..."` and review the generated migration.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import REAL, BigInteger, ForeignKey, Index, MetaData, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Matches PostgreSQL's default constraint names, so names are predictable in migrations.
NAMING_CONVENTION = {
    "ix": "%(table_name)s_%(column_0_name)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        str: Text,
        float: REAL,
        dict[str, Any]: JSONB,
        list[str]: ARRAY(Text),
        datetime: TIMESTAMP(timezone=True),
    }


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
        Index("products_category_idx", "category", postgresql_where=text("active")),
        Index("products_brand_idx", "brand", postgresql_where=text("active")),
        Index("products_price_idx", "price_value", postgresql_where=text("active")),
    )


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
        Index("product_compatibility_lookup_idx", "dimension", "canonical_value", "status"),
        Index("product_compatibility_product_idx", "product_id"),
    )


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
        Index("product_requirements_product_idx", "product_id"),
        Index("product_requirements_item_idx", "canonical_item"),
    )


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


class RetrievalDocumentRecord(Base):
    __tablename__ = "retrieval_documents"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    text: Mapped[str]
    doc_hash: Mapped[str]
    indexed_doc_hash: Mapped[str | None]
    embedding_model: Mapped[str | None]
    indexed_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class IngestionRunRecord(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(server_default=text("'running'"))
    args: Mapped[dict[str, Any]]
    stats: Mapped[dict[str, Any] | None]
