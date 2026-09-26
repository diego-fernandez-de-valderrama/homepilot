"""SQLAlchemy models of the customer memory database. Only `repositories/profile.py` uses them.

After editing, run `uv run alembic revision --autogenerate -m "..."` from smart-home-agent and review the file.
"""

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import BigInteger, Index, MetaData, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
    type_annotation_map: ClassVar[dict[Any, Any]] = {str: Text, datetime: TIMESTAMP(timezone=True)}


class CustomerFactRecord(Base):
    """One fact a customer stated about themself. Retracted facts stay (active=false) for provenance."""

    __tablename__ = "customer_facts"
    __table_args__ = (
        Index("customer_facts_user_id_idx", "user_id"),
        # One active fact per value; a retracted one may be stated again later.
        Index(
            "customer_facts_active_value_key", "user_id", "kind", "value", unique=True, postgresql_where=text("active")
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str]
    kind: Mapped[str]  # models.profile.FactKind value
    value: Mapped[str]
    canonical: Mapped[str | None]
    label: Mapped[str]
    evidence: Mapped[str]  # verbatim quote from the customer's message
    session_id: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    retracted_at: Mapped[datetime | None]
    retracted_evidence: Mapped[str | None]
