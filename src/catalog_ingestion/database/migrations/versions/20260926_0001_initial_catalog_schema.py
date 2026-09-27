"""Initial catalog schema.

Products (typed filter columns + JSONB documents), compatibility facts, requirements,
web page cache, retrieval documents and ingestion runs.

Revision ID: 0001
Revises:
Create Date: 2026-09-26 11:47:57.391570
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'running'"), nullable=False),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("ingestion_runs_pkey")),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("category_slug", sa.Text(), nullable=True),
        sa.Column("product_type", sa.Text(), nullable=True),
        sa.Column("is_smart_home", sa.Boolean(), nullable=True),
        sa.Column("price_value", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("price_currency", sa.Text(), nullable=True),
        sa.Column("original_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("ean", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("summary_en", sa.Text(), nullable=True),
        sa.Column("summary_de", sa.Text(), nullable=True),
        sa.Column("completeness_level", sa.Text(), nullable=False),
        sa.Column("completeness_score", sa.REAL(), nullable=False),
        sa.Column("web_status", sa.Text(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("llm_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_hash", sa.Text(), nullable=False),
        sa.Column("document_hash", sa.Text(), nullable=False),
        sa.Column("enrichment_hash", sa.Text(), nullable=True),
        sa.Column("enrichment_model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("products_pkey")),
    )
    op.create_index("products_brand_idx", "products", ["brand"], unique=False, postgresql_where=sa.text("active"))
    op.create_index("products_category_idx", "products", ["category"], unique=False, postgresql_where=sa.text("active"))
    op.create_index("products_price_idx", "products", ["price_value"], unique=False, postgresql_where=sa.text("active"))
    op.create_table(
        "web_pages",
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("fetched_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("url", name=op.f("web_pages_pkey")),
    )
    op.create_table(
        "product_compatibility",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("canonical_value", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_field", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("product_compatibility_product_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("product_compatibility_pkey")),
    )
    op.create_index(
        "product_compatibility_lookup_idx",
        "product_compatibility",
        ["dimension", "canonical_value", "status"],
        unique=False,
    )
    op.create_index("product_compatibility_product_idx", "product_compatibility", ["product_id"], unique=False)
    op.create_table(
        "product_requirements",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("item", sa.Text(), nullable=False),
        sa.Column("canonical_item", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("necessity", sa.Text(), nullable=False),
        sa.Column("alternatives", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_field", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("product_requirements_product_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("product_requirements_pkey")),
    )
    op.create_index("product_requirements_item_idx", "product_requirements", ["canonical_item"], unique=False)
    op.create_index("product_requirements_product_idx", "product_requirements", ["product_id"], unique=False)
    op.create_table(
        "retrieval_documents",
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("doc_hash", sa.Text(), nullable=False),
        sa.Column("indexed_doc_hash", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("indexed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("retrieval_documents_product_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("product_id", name=op.f("retrieval_documents_pkey")),
    )


def downgrade() -> None:
    op.drop_table("retrieval_documents")
    op.drop_index("product_requirements_product_idx", table_name="product_requirements")
    op.drop_index("product_requirements_item_idx", table_name="product_requirements")
    op.drop_table("product_requirements")
    op.drop_index("product_compatibility_product_idx", table_name="product_compatibility")
    op.drop_index("product_compatibility_lookup_idx", table_name="product_compatibility")
    op.drop_table("product_compatibility")
    op.drop_table("web_pages")
    op.drop_index("products_price_idx", table_name="products", postgresql_where=sa.text("active"))
    op.drop_index("products_category_idx", table_name="products", postgresql_where=sa.text("active"))
    op.drop_index("products_brand_idx", table_name="products", postgresql_where=sa.text("active"))
    op.drop_table("products")
    op.drop_table("ingestion_runs")
