from datetime import datetime

from sqlalchemy import BigInteger, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from smart_home_agent.repositories.profile._records.memory_base import MemoryBase


class CustomerFactRecord(MemoryBase):
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
