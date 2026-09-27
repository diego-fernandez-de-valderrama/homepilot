from collections.abc import Sequence

from catalog_ingestion.core.settings import PostgresSettings
from catalog_ingestion.storage.postgres.engine import create_db_engine, create_session_factory
from catalog_ingestion.storage.postgres.models import ProductRecord
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from smart_home_agent.models import Product, ProductFilter
from smart_home_agent.repositories.catalog._product_mapper import ProductMapper
from smart_home_agent.repositories.catalog._product_query import ProductQuery


class CatalogRepository:
    """`CatalogReader` over PostgreSQL. Every public method returns business models, never ORM records."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    @staticmethod
    def readonly_sessions(settings: PostgresSettings) -> tuple[Engine, sessionmaker[Session]]:
        """Engine whose transactions are READ ONLY: the agent can never modify the catalog."""
        engine = create_db_engine(settings).execution_options(postgresql_readonly=True)
        return engine, create_session_factory(engine)

    def get_products(self, product_ids: Sequence[str]) -> list[Product]:
        """Active products for the given ids, in the order of `product_ids` (unknown ids are skipped)."""
        if not product_ids:
            return []
        statement = ProductQuery.with_children(
            select(ProductRecord).where(ProductRecord.active, ProductRecord.id.in_(list(product_ids)))
        )
        with self._sessions() as session:
            by_id = {record.id: ProductMapper.to_product(record) for record in session.scalars(statement)}
        return [by_id[pid] for pid in dict.fromkeys(product_ids) if pid in by_id]

    def get_product(self, product_id: str) -> Product | None:
        products = self.get_products([product_id])
        return products[0] if products else None

    def get_versions(self, titles: Sequence[str]) -> dict[str, list[Product]]:
        """Active products per title (the versions of one product share it), cheapest first."""
        if not titles:
            return {}
        statement = ProductQuery.with_children(
            select(ProductRecord)
            .where(ProductRecord.active, ProductRecord.title.in_(list(dict.fromkeys(titles))))
            .order_by(ProductRecord.price_value.asc().nulls_last(), ProductRecord.id)
        )
        versions: dict[str, list[Product]] = {}
        with self._sessions() as session:
            for record in session.scalars(statement):
                versions.setdefault(record.title, []).append(ProductMapper.to_product(record))
        return versions

    def filter_products(self, criteria: ProductFilter) -> tuple[int, list[Product]]:
        """(total number of matches, first `limit` matches)."""
        conditions = ProductQuery.conditions(criteria)
        statement = ProductQuery.with_children(
            ProductQuery.ordered(select(ProductRecord).where(*conditions), criteria).limit(criteria.limit)
        )
        with self._sessions() as session:
            total = session.scalar(select(func.count()).select_from(ProductRecord).where(*conditions)) or 0
            products = [ProductMapper.to_product(record) for record in session.scalars(statement)]
        return total, products

    def count_active(self) -> int:
        with self._sessions() as session:
            return session.scalar(select(func.count()).select_from(ProductRecord).where(ProductRecord.active)) or 0
