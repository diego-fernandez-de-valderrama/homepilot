"""Customer memory storage: the agent's own PostgreSQL database (schema via SQLAlchemy + Alembic).

It lives next to the catalog on the same server but in a separate database (AGENT_MEMORY_DB), so the catalog
engine stays read-only. `python -m smart_home_agent init-memory` creates the database and migrates it.
"""
