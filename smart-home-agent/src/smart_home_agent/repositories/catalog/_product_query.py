from catalog_ingestion.database import CompatibilityRecord, ProductRecord
from catalog_ingestion.vocabulary import FactStatus
from sqlalchemy import ColumnElement, ColumnExpressionArgument, Select, and_, exists, func, or_
from sqlalchemy.orm import selectinload

from smart_home_agent.models import ProductFilter


class ProductQuery:
    """SQL building blocks for product reads: `ProductFilter` -> WHERE conditions, ordering, eager loading."""

    @staticmethod
    def conditions(criteria: ProductFilter) -> list[ColumnExpressionArgument[bool]]:
        """Only active products, then every criterion that is set (all must hold)."""
        conditions: list[ColumnExpressionArgument[bool]] = [ProductRecord.active]
        if criteria.category:
            conditions.append(ProductRecord.category == criteria.category)
        if criteria.min_price is not None:
            conditions.append(ProductRecord.price_value >= criteria.min_price)
        if criteria.max_price is not None:
            conditions.append(ProductRecord.price_value <= criteria.max_price)
        if criteria.brands:
            conditions.append(or_(*(ProductQuery.brand_condition(b) for b in criteria.brands)))
        conditions.extend(ProductQuery.supported_condition(canonical) for canonical in criteria.supports)
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

    @staticmethod
    def ordered(statement: Select[ProductRecord], criteria: ProductFilter) -> Select[ProductRecord]:
        match criteria.sort:
            case "price_asc":
                return statement.order_by(ProductRecord.price_value.asc().nulls_last(), ProductRecord.id)
            case "price_desc":
                return statement.order_by(ProductRecord.price_value.desc().nulls_last(), ProductRecord.id)
            case _:
                return statement.order_by(ProductRecord.completeness_score.desc(), ProductRecord.id)

    @staticmethod
    def with_children(statement: Select[ProductRecord]) -> Select[ProductRecord]:
        """Loads the compatibility and requirement rows that `ProductMapper.to_product` reads."""
        return statement.options(selectinload(ProductRecord.compatibility), selectinload(ProductRecord.requirements))

    @staticmethod
    def brand_condition(brand: str) -> ColumnElement[bool]:
        """Case-insensitive brand match; a brand also matches its sub-brands ("Philips" -> "Philips Hue")."""
        wanted = brand.strip().casefold()
        column = func.lower(ProductRecord.brand)
        return or_(column == wanted, column.startswith(f"{wanted} ", autoescape=True))

    @staticmethod
    def supported_condition(canonical: str) -> ColumnElement[bool]:
        """A `supported` fact exists and no `unsupported` fact contradicts it (same rule as the compatibility
        service)."""
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
