"""SQLAlchemy records of the customer memory database. Only this package's repository and migrations use them.

After editing, run `uv run alembic revision --autogenerate -m "..."` from smart-home-agent and review the file.
"""

from smart_home_agent.repositories.profile._records.customer_fact_record import CustomerFactRecord
from smart_home_agent.repositories.profile._records.memory_base import MemoryBase

__all__ = ["CustomerFactRecord", "MemoryBase"]
