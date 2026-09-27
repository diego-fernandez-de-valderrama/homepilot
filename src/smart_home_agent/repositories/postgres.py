"""Read-only access to the PostgreSQL catalog through SQLAlchemy.

The ORM models are the ones owned by `catalog-ingestion` (it also owns the migrations).
Every public method returns Pydantic business models; ORM objects never leave this module.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from catalog_ingestion.core.settings import PostgresSettings
from catalog_ingestion.domain.enums import FactStatus
from catalog_ingestion.schemas.catalog_product import CatalogProductSchema
from catalog_ingestion.schemas.raw_product import RawProductSchema
from catalog_ingestion.storage.postgres.engine import create_db_engine, create_session_factory
from catalog_ingestion.storage.postgres.models import CompatibilityRecord, ProductRecord, RequirementRecord
from catalog_ingestion.vocabulary.requirements import term_by_canonical
from sqlalchemy import ColumnElement, ColumnExpressionArgument, Engine, Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from smart_home_agent.models import (
    CompatibilityFact,
    Evidence,
    FieldProvenance,
    Product,
    ProductFilter,
    ProductRequirement,
    Spec,
)


class CatalogReader(Protocol):
    """What the services need from the structured catalog."""

    def get_products(self, product_ids: Sequence[str]) -> list[Product]: ...

    def get_product(self, product_id: str) -> Product | None: ...

    def filter_products(self, criteria: ProductFilter) -> tuple[int, list[Product]]: ...

    def get_versions(self, titles: Sequence[str]) -> dict[str, list[Product]]: ...


def create_readonly_sessions(settings: PostgresSettings) -> tuple[Engine, sessionmaker[Session]]:
    """Engine whose transactions are READ ONLY: the agent can never modify the catalog."""
    engine = create_db_engine(settings).execution_options(postgresql_readonly=True)
    return engine, create_session_factory(engine)


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _evidence(record: CompatibilityRecord | RequirementRecord) -> Evidence:
    return Evidence(
        source=record.source,
        text=record.evidence,
        field=record.source_field,
        url=record.source_url,
        method=record.method,
        confidence=record.confidence,
    )


def _fact(record: CompatibilityRecord) -> CompatibilityFact:
    return CompatibilityFact(
        dimension=record.dimension,
        canonical_value=record.canonical_value,
        label=record.label,
        raw_value=record.raw_value,
        status=record.status,
        evidence=_evidence(record),
    )


def _requirement(record: RequirementRecord) -> ProductRequirement:
    term = term_by_canonical(record.canonical_item)
    return ProductRequirement(
        item=record.item,
        canonical_item=record.canonical_item,
        label=term.label if term else record.item,
        kind=record.kind,
        necessity=record.necessity,
        alternatives=list(record.alternatives),
        evidence=_evidence(record),
    )


def own_variant(subtitle: str | None, options: Sequence[str]) -> str | None:
    """The option label of this version: the longest shop option that its subtitle contains ("Weiß" in
    "GU10, Dimmbar, RGBW, 350 lm, 4,8 W, Weiß"). None when the subtitle names none of them."""
    text = (subtitle or "").casefold()
    matches = [option for option in options if option.casefold() in text]
    return max(matches, key=len) if matches else None


def to_product(record: ProductRecord) -> Product:
    """ORM row -> business model. Typed columns and child tables win; the JSONB document adds
    the enriched descriptive fields (specs, features, provenance), the untouched raw input the
    version fields (subtitle and the shop's variant options)."""
    document = CatalogProductSchema.model_validate(record.document)
    raw = RawProductSchema.model_validate(record.raw)
    subtitle = raw.subtitle.strip() or None
    options = [option.strip() for option in raw.variants if option.strip()]
    return Product(
        id=record.id,
        title=record.title,
        brand=record.brand,
        category=record.category,
        category_label_en=document.category_label_en,
        category_label_de=document.category_label_de,
        product_type=record.product_type,
        price=_float(record.price_value),
        currency=record.price_currency,
        original_price=_float(record.original_price),
        price_raw=document.price.raw,
        summary_en=record.summary_en,
        summary_de=record.summary_de,
        source_url=record.source_url,
        subtitle=subtitle,
        variant=own_variant(subtitle, options),
        variant_options=options,
        ean=record.ean,
        image_url=record.image_url,
        is_smart_home=record.is_smart_home,
        completeness_level=record.completeness_level,
        completeness_score=record.completeness_score,
        key_features=document.key_features,
        use_cases=document.use_cases,
        specs=[Spec(name=s.name, value=s.value, unit=s.unit) for s in document.specs],
        compatibility=[_fact(r) for r in record.compatibility],
        requirements=[_requirement(r) for r in record.requirements],
        attributes=record.attributes,
        provenance=[FieldProvenance.model_validate(p.model_dump()) for p in document.provenance],
        validation_notes=document.validation_notes,
    )


def brand_condition(brand: str) -> ColumnElement[bool]:
    """Case-insensitive brand match; a brand also matches its sub-brands ("Philips" -> "Philips Hue")."""
    wanted = brand.strip().casefold()
    column = func.lower(ProductRecord.brand)
    return or_(column == wanted, column.startswith(f"{wanted} ", autoescape=True))


def supported_condition(canonical: str) -> ColumnElement[bool]:
    """A `supported` fact exists and no `unsupported` fact contradicts it (same rule as the compatibility service)."""
    fact = CompatibilityRecord
    supported = exists().where(
        fact.product_id == ProductRecord.id,
        fact.canonical_value == canonical,
        fact.status == FactStatus.SUPPORTED.value,
    )
    unsupported = exists().where(
        fact.product_id == ProductRecord.id,
        fact.canonical_value == canonical,
        fact.status == FactStatus.UNSUPPORTED.value,
    )
    return and_(supported, ~unsupported)


def _conditions(criteria: ProductFilter) -> list[ColumnExpressionArgument[bool]]:
    conditions: list[ColumnExpressionArgument[bool]] = [ProductRecord.active]
    if criteria.category:
        conditions.append(ProductRecord.category == criteria.category)
    if criteria.min_price is not None:
        conditions.append(ProductRecord.price_value >= criteria.min_price)
    if criteria.max_price is not None:
        conditions.append(ProductRecord.price_value <= criteria.max_price)
    if criteria.brands:
        conditions.append(or_(*(brand_condition(b) for b in criteria.brands)))
    conditions.extend(supported_condition(canonical) for canonical in criteria.supports)
    if criteria.product_type_contains:
        pattern = criteria.product_type_contains.strip()
        conditions.append(
            or_(
                ProductRecord.product_type.icontains(pattern, autoescape=True),
                ProductRecord.title.icontains(pattern, autoescape=True),
            )
        )
    if criteria.product_ids is not None:
        conditions.append(ProductRecord.id.in_(criteria.product_ids))
    return conditions


def _ordered(statement: Select[ProductRecord], criteria: ProductFilter) -> Select[ProductRecord]:
    match criteria.sort:
        case "price_asc":
            return statement.order_by(ProductRecord.price_value.asc().nulls_last(), ProductRecord.id)
        case "price_desc":
            return statement.order_by(ProductRecord.price_value.desc().nulls_last(), ProductRecord.id)
        case _:
            return statement.order_by(ProductRecord.completeness_score.desc(), ProductRecord.id)


def _with_children(statement: Select[ProductRecord]) -> Select[ProductRecord]:
    return statement.options(selectinload(ProductRecord.compatibility), selectinload(ProductRecord.requirements))


class CatalogRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get_products(self, product_ids: Sequence[str]) -> list[Product]:
        """Active products for the given ids, in the order of `product_ids` (unknown ids are skipped)."""
        if not product_ids:
            return []
        statement = _with_children(
            select(ProductRecord).where(ProductRecord.active, ProductRecord.id.in_(list(product_ids)))
        )
        with self._sessions() as session:
            by_id = {record.id: to_product(record) for record in session.scalars(statement)}
        return [by_id[pid] for pid in dict.fromkeys(product_ids) if pid in by_id]

    def get_product(self, product_id: str) -> Product | None:
        products = self.get_products([product_id])
        return products[0] if products else None

    def get_versions(self, titles: Sequence[str]) -> dict[str, list[Product]]:
        """Active products per title (the versions of one product share it), cheapest first."""
        if not titles:
            return {}
        statement = _with_children(
            select(ProductRecord)
            .where(ProductRecord.active, ProductRecord.title.in_(list(dict.fromkeys(titles))))
            .order_by(ProductRecord.price_value.asc().nulls_last(), ProductRecord.id)
        )
        versions: dict[str, list[Product]] = {}
        with self._sessions() as session:
            for record in session.scalars(statement):
                versions.setdefault(record.title, []).append(to_product(record))
        return versions

    def filter_products(self, criteria: ProductFilter) -> tuple[int, list[Product]]:
        """(total number of matches, first `limit` matches)."""
        conditions = _conditions(criteria)
        statement = _with_children(_ordered(select(ProductRecord).where(*conditions), criteria).limit(criteria.limit))
        with self._sessions() as session:
            total = session.scalar(select(func.count()).select_from(ProductRecord).where(*conditions)) or 0
            products = [to_product(record) for record in session.scalars(statement)]
        return total, products

    def count_active(self) -> int:
        with self._sessions() as session:
            return session.scalar(select(func.count()).select_from(ProductRecord).where(ProductRecord.active)) or 0
