from decimal import Decimal

from catalog_ingestion.normalization.normalizer import category_slug_from_url
from tests.conftest import DISCOUNTED, RICH_SCHELLENBERG, SPARSE_MATTER, load_normalized


def test_sparse_product_is_normalized_without_description_or_attributes():
    product = load_normalized(SPARSE_MATTER)
    assert product.source_url is not None and not product.source_url.endswith("\n")
    assert product.category_slug == "smart-home-fensterkontakte-tuerkontakte"
    assert product.category == "contact_sensor"
    assert product.brand == "Bosch"
    assert product.price.value == Decimal("124.95")
    assert product.variants == ("1 Stk.", "3 Stk.")
    assert product.description.is_empty
    assert product.attributes.is_empty
    assert product.is_smart_home is None  # unknown, never False from absence
    assert product.ean is None


def test_rich_product_fields():
    product = load_normalized(RICH_SCHELLENBERG)
    assert product.category_slug == "rollladensteuerung"
    assert product.category == "shutter_blind_control"
    assert product.is_smart_home is True
    assert product.ean == "4003971200178"


def test_discounted_product():
    product = load_normalized(DISCOUNTED)
    assert product.price.value is not None
    assert product.price.original_value is not None
    assert product.price.value < product.price.original_value


def test_category_slug_from_url():
    assert category_slug_from_url("https://www.bauhaus.info/led-lampen/philips-x/p/123") == "led-lampen"
    assert category_slug_from_url("https://example.com/") is None
