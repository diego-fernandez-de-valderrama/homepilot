"""Customer memory: the agent's own writable PostgreSQL database (schema via SQLAlchemy + Alembic).

It lives next to the catalog on the same server but in a separate database (AGENT_MEMORY_DB), so the catalog
engine stays read-only. Flow:

- `MemoryDatabase`: creates the database, builds its writable engine and migrates it (`migrations/`, also used by
  `uv run alembic ...`). `python -m smart_home_agent init-memory` runs `ensure_exists` + `upgrade_to_head`.
- `ProfileStore`: the protocol the profile service depends on.
- `ProfileRepository`: its implementation. It reads and writes the private `_records` (`CustomerFactRecord`) and
  maps them with the private `FactMapper`; ORM records never leave this package.
"""

from smart_home_agent.repositories.profile.memory_database import MemoryDatabase
from smart_home_agent.repositories.profile.profile_repository import ProfileRepository
from smart_home_agent.repositories.profile.profile_store import ProfileStore

__all__ = ["MemoryDatabase", "ProfileRepository", "ProfileStore"]
