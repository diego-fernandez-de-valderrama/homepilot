"""Against the live catalog (read-only). These assert structure and rules, not exact catalog content."""

import pytest
from catalog_ingestion.vocabulary import FactStatus
from sqlalchemy import text
from sqlalchemy.exc import InternalError

from smart_home_agent.models import Product, ProductFilter
from smart_home_agent.services import CompatibilityEvaluator, Vocabulary

pytestmark = pytest.mark.integration


def test_orm_rows_map_to_business_models(catalog):
    _, products = catalog.filter_products(ProductFilter(limit=5))
    assert products
    assert all(isinstance(p, Product) for p in products)
    assert catalog.get_product(products[0].id).id == products[0].id
    assert catalog.get_product("does-not-exist") is None


def test_get_products_keeps_the_requested_order(catalog):
    _, products = catalog.filter_products(ProductFilter(limit=3))
    ids = [p.id for p in reversed(products)]
    assert [p.id for p in catalog.get_products(ids)] == ids


def test_price_category_and_brand_filters(catalog):
    total, products = catalog.filter_products(
        ProductFilter(category="heating_control", max_price=150, sort="price_asc", limit=50)
    )
    assert total >= len(products) > 0
    assert all(p.category == "heating_control" and p.price is not None and p.price <= 150 for p in products)
    prices = [p.price for p in products]
    assert prices == sorted(prices)
    _, bosch = catalog.filter_products(ProductFilter(brands=["bosch"], limit=50))
    assert all(p.brand and p.brand.casefold().startswith("bosch") for p in bosch)


def test_supports_filter_agrees_with_the_compatibility_service(catalog):
    _, products = catalog.filter_products(
        ProductFilter(category="heating_control", supports=["google_home"], limit=100)
    )
    assert products
    google_home = Vocabulary.term("google_home")
    assert all(CompatibilityEvaluator.evaluate(p, [google_home]).overall is FactStatus.SUPPORTED for p in products)


def test_google_assistant_products_are_not_google_home_products(catalog):
    _, assistant = catalog.filter_products(
        ProductFilter(category="heating_control", supports=["google_assistant"], limit=200)
    )
    google_home = Vocabulary.term("google_home")
    statuses = {CompatibilityEvaluator.evaluate(p, [google_home]).overall for p in assistant}
    assert FactStatus.UNKNOWN in statuses  # many support the assistant without confirming Google Home
    assert FactStatus.UNSUPPORTED not in statuses  # absence of evidence never becomes "unsupported"


def test_sessions_are_read_only(catalog):
    with catalog._sessions() as session, pytest.raises(InternalError):
        session.execute(text("UPDATE products SET title = title WHERE false"))


def test_versions_share_the_title_and_carry_their_own_variant(catalog):
    _, products = catalog.filter_products(ProductFilter(limit=500))
    assert any(p.subtitle for p in products)  # read from the untouched raw input
    with_options = [p for p in products if len(p.variant_options) > 1]
    versions = catalog.get_versions([p.title for p in with_options])
    families = [family for family in versions.values() if len(family) > 1]
    assert families, "the catalog has products sold in several versions"
    for family in families:
        assert len({p.title for p in family}) == 1
        prices = [p.price for p in family if p.price is not None]
        assert prices == sorted(prices)  # cheapest first
        for p in family:
            if p.variant:
                assert p.variant in p.variant_options
                assert p.variant.casefold() in (p.subtitle or "").casefold()
    assert catalog.get_versions([]) == {}
    assert catalog.get_versions(["no such title"]) == {}
