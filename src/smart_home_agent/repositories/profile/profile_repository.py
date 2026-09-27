from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func

from smart_home_agent.models import CustomerFact, CustomerProfile, CustomerSummary, NewFact
from smart_home_agent.repositories.profile._fact_mapper import FactMapper
from smart_home_agent.repositories.profile._records import CustomerFactRecord


class ProfileRepository:
    """`ProfileStore` over the customer memory database. ORM records never leave this class."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def load(self, user_id: str, include_retracted: bool = False) -> CustomerProfile:
        query = select(CustomerFactRecord).where(CustomerFactRecord.user_id == user_id)
        if not include_retracted:
            query = query.where(CustomerFactRecord.active)
        with self._sessions() as session:
            records = session.scalars(query.order_by(CustomerFactRecord.created_at, CustomerFactRecord.id)).all()
            return CustomerProfile(user_id=user_id, facts=[FactMapper.to_fact(r) for r in records])

    def customers(self) -> list[CustomerSummary]:
        """Every customer with at least one stored fact, most recently active first."""
        record = CustomerFactRecord
        last_activity = func.max(
            func.greatest(record.created_at, func.coalesce(record.retracted_at, record.created_at))
        )
        query = (
            select(
                record.user_id,
                func.count().filter(record.active).label("active_facts"),
                func.count().label("total_facts"),
                last_activity.label("last_activity"),
            )
            .group_by(record.user_id)
            .order_by(last_activity.desc(), record.user_id)
        )
        with self._sessions() as session:
            return [
                CustomerSummary(user_id=user_id, active_facts=active, total_facts=total, last_activity=last)
                for user_id, active, total, last in session.execute(query).all()
            ]

    def apply(
        self,
        user_id: str,
        session_id: str | None,
        evidence: str,
        add: Sequence[NewFact],
        retract_ids: Sequence[int],
    ) -> tuple[list[CustomerFact], list[CustomerFact]]:
        """Retracts and adds in one transaction; returns (added, retracted)."""
        with self._sessions.begin() as session:
            retracted = self._retract(session, user_id, evidence, retract_ids)
            added = self._add(session, user_id, session_id, evidence, add)
            return [FactMapper.to_fact(r) for r in added], [FactMapper.to_fact(r) for r in retracted]

    def delete_customers(self, user_ids: Sequence[str]) -> int:
        """Removes every fact of these customers (evaluation cleanup; customers only ever retract)."""
        if not user_ids:
            return 0
        with self._sessions.begin() as session:
            query = delete(CustomerFactRecord).where(CustomerFactRecord.user_id.in_(user_ids))
            return len(session.scalars(query.returning(CustomerFactRecord.id)).all())

    @staticmethod
    def _retract(session: Session, user_id: str, evidence: str, retract_ids: Sequence[int]) -> list[CustomerFactRecord]:
        """Marks the customer's active facts with these ids inactive (the rows stay for provenance)."""
        if not retract_ids:
            return []
        return list(
            session.scalars(
                update(CustomerFactRecord)
                .where(
                    CustomerFactRecord.user_id == user_id,
                    CustomerFactRecord.id.in_(retract_ids),
                    CustomerFactRecord.active,
                )
                .values(active=False, retracted_at=func.now(), retracted_evidence=evidence)
                .returning(CustomerFactRecord)
            )
        )

    @staticmethod
    def _add(
        session: Session, user_id: str, session_id: str | None, evidence: str, facts: Sequence[NewFact]
    ) -> list[CustomerFactRecord]:
        """Inserts the new facts and reloads them (ids and server defaults)."""
        added = [
            CustomerFactRecord(
                user_id=user_id,
                kind=fact.kind.value,
                value=fact.value,
                canonical=fact.canonical,
                label=fact.label,
                evidence=evidence,
                session_id=session_id,
            )
            for fact in facts
        ]
        session.add_all(added)
        session.flush()
        for record in added:
            session.refresh(record)
        return added
