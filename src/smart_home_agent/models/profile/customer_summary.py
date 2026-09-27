from datetime import datetime

from pydantic import BaseModel


class CustomerSummary(BaseModel):
    """A customer with something stored, for picking test customers in the interface."""

    user_id: str
    active_facts: int
    total_facts: int
    last_activity: datetime
