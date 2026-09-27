"""Data access below the services. Import everything from here:

    from smart_home_agent.repositories import CatalogReader, SemanticIndex, ProfileStore, ...

Each subpackage offers a protocol (what the services depend on) and its implementation (built in `container.py`).
They return Pydantic business models from `smart_home_agent.models`; ORM records and Qdrant payloads never leave
them.

- `catalog/`: the product catalog in PostgreSQL, read-only (`CatalogReader`, `CatalogRepository`). The source of
  truth for prices, compatibility and filtering.
- `semantic/`: product discovery in Qdrant (`SemanticIndex`, `QdrantIndex`). Only ids and scores.
- `profile/`: customer memory, the agent's own writable database (`ProfileStore`, `ProfileRepository`) and its
  creation and migrations (`MemoryDatabase`).
"""

from smart_home_agent.repositories.catalog import CatalogReader, CatalogRepository
from smart_home_agent.repositories.profile import MemoryDatabase, ProfileRepository, ProfileStore
from smart_home_agent.repositories.semantic import QdrantIndex, SemanticIndex

__all__ = [
    "CatalogReader",
    "CatalogRepository",
    "MemoryDatabase",
    "ProfileRepository",
    "ProfileStore",
    "QdrantIndex",
    "SemanticIndex",
]
