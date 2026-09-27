import pytest
from pydantic import ValidationError

from smart_home_agent.models import ProductFilter
from smart_home_agent.services.filtering import brand_matches, rejection_reason
from tests.fakes import FakeCatalog, fact, product


def test_price_bounds():
    criteria = ProductFilter(min_price=20, max_price=100)
    assert rejection_reason(product("1", price=50), criteria) is None
    assert rejection_reason(product("2", price=100), criteria) is None  # inclusive
    assert rejection_reason(product("3", price=150), criteria) == "price"
    assert rejection_reason(product("4", price=10), criteria) == "price"


def test_unknown_price_never_passes_a_budget():
    assert rejection_reason(product("1", price=None), ProductFilter(max_price=100)) == "price_unknown"
    assert rejection_reason(product("1", price=None), ProductFilter()) is None


def test_category():
    assert (
        rejection_reason(product("1", category="smart_plug"), ProductFilter(category="heating_control")) == "category"
    )
    assert rejection_reason(product("1"), ProductFilter(category="heating_control")) is None


def test_brand_is_case_insensitive_and_matches_sub_brands():
    assert brand_matches("Philips Hue", ["philips"])
    assert brand_matches("Bosch", ["BOSCH"])
    assert not brand_matches("Philipsen", ["philips"])
    assert not brand_matches(None, ["bosch"])
    assert brand_matches(None, [])
    assert rejection_reason(product("1", brand="Ledvance"), ProductFilter(brands=["Bosch"])) == "brand"


def test_invalid_price_range_is_rejected():
    with pytest.raises(ValidationError):
        ProductFilter(min_price=100, max_price=10)
    with pytest.raises(ValidationError):
        ProductFilter(max_price=-1)


def test_protocol_filter_needs_explicit_support():
    catalog = FakeCatalog(
        [product("zigbee", facts=[fact("zigbee")]), product("wifi", facts=[fact("wifi")]), product("unknown")]
    )
    total, products = catalog.filter_products(ProductFilter(supports=["zigbee"]))
    assert total == 1
    assert [p.id for p in products] == ["zigbee"]
