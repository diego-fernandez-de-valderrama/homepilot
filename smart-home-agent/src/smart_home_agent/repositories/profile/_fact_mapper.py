from smart_home_agent.models import CustomerFact, FactKind
from smart_home_agent.repositories.profile._records import CustomerFactRecord


class FactMapper:
    """ORM record -> business model. The only place that turns customer memory records into Pydantic models."""

    @staticmethod
    def to_fact(record: CustomerFactRecord) -> CustomerFact:
        return CustomerFact(
            id=record.id,
            user_id=record.user_id,
            kind=FactKind(record.kind),
            value=record.value,
            canonical=record.canonical,
            label=record.label,
            evidence=record.evidence,
            session_id=record.session_id,
            created_at=record.created_at,
            active=record.active,
            retracted_at=record.retracted_at,
            retracted_evidence=record.retracted_evidence,
        )
