"""Customer facts.

Facts customers stated about themselves (name, language, ecosystems, owned devices, preferences), per user id,
with the verbatim evidence. Retracted facts stay with active=false.

Revision ID: 0001
Revises:
Create Date: 2026-09-26 18:00:00.000000
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
        "customer_facts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("canonical", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("retracted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("retracted_evidence", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("customer_facts_pkey")),
    )
    op.create_index(
        "customer_facts_active_value_key",
        "customer_facts",
        ["user_id", "kind", "value"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_index("customer_facts_user_id_idx", "customer_facts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("customer_facts_user_id_idx", table_name="customer_facts")
    op.drop_index("customer_facts_active_value_key", table_name="customer_facts", postgresql_where=sa.text("active"))
    op.drop_table("customer_facts")
