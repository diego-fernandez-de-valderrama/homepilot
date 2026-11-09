from collections.abc import Sequence
from typing import Protocol

from smart_home_agent.models import CustomerFact, CustomerProfile, CustomerSummary, NewFact


class ProfileStore(Protocol):
    """What the profile service needs from the customer memory."""

    def load(self, user_id: str, include_retracted: bool = False) -> CustomerProfile: ...

    def customers(self) -> list[CustomerSummary]:
        """Every customer with at least one stored fact, most recently active first."""
        ...

    def apply(
        self,
        user_id: str,
        session_id: str | None,
        evidence: str,
        add: Sequence[NewFact],
        retract_ids: Sequence[int],
    ) -> tuple[list[CustomerFact], list[CustomerFact]]:
        """Retracts and adds in one transaction; returns (added, retracted)."""
        ...
