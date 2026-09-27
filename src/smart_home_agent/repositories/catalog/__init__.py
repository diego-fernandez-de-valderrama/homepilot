"""Read-only access to the PostgreSQL catalog through SQLAlchemy.

The ORM records are owned by `catalog-ingestion` (it also owns the migrations); they never leave this package.

- `CatalogReader`: the protocol the services depend on.
- `CatalogRepository`: its PostgreSQL implementation (`readonly_sessions` builds the READ ONLY engine).
  It builds statements with the private `ProductQuery` (`ProductFilter` -> SQL) and maps every row with the
  private `ProductMapper` (ORM record -> `Product`, incl. the version fields `subtitle`/`variant`).
"""

from smart_home_agent.repositories.catalog.catalog_reader import CatalogReader
from smart_home_agent.repositories.catalog.catalog_repository import CatalogRepository

__all__ = ["CatalogReader", "CatalogRepository"]
