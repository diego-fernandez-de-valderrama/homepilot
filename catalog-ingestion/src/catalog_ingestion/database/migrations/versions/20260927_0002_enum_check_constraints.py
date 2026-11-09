"""CHECK constraints on enum-like text columns.

"Unknown stays unknown" and the provenance vocabulary were only enforced in Python; a bad write
(for example "Supported") is now rejected by PostgreSQL. The allowed values are frozen here on purpose:
a new enum value needs its own migration.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27 02:40:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = ("catalog", "web", "llm")
_METHODS = ("deterministic", "llm")
_CONSTRAINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "products": {
        "completeness_level": ("rich", "partial", "sparse"),
        "web_status": ("not_needed", "skipped", "ok", "failed"),
    },
    "product_compatibility": {
        "dimension": ("ecosystem", "voice_assistant", "protocol", "mobile_os", "control"),
        "status": ("supported", "unsupported", "unknown"),
        "source": _SOURCES,
        "method": _METHODS,
    },
    "product_requirements": {
        "kind": (
            "hub",
            "gateway",
            "app",
            "subscription",
            "network",
            "device",
            "professional_installation",
            "other",
        ),
        "necessity": ("required", "required_for_some_features"),
        "source": _SOURCES,
        "method": _METHODS,
    },
}
_CONFIDENCE_TABLES = ("product_compatibility", "product_requirements")


def upgrade() -> None:
    for table, columns in _CONSTRAINTS.items():
        for column, values in columns.items():
            allowed = ", ".join(f"'{value}'" for value in values)
            op.create_check_constraint(op.f(f"{table}_{column}_check"), table, f"{column} IN ({allowed})")
    for table in _CONFIDENCE_TABLES:
        op.create_check_constraint(op.f(f"{table}_confidence_check"), table, "confidence BETWEEN 0 AND 1")


def downgrade() -> None:
    for table in _CONFIDENCE_TABLES:
        op.drop_constraint(op.f(f"{table}_confidence_check"), table, type_="check")
    for table, columns in _CONSTRAINTS.items():
        for column in columns:
            op.drop_constraint(op.f(f"{table}_{column}_check"), table, type_="check")
