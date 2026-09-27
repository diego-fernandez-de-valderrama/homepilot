from decimal import Decimal

import pytest

from catalog_ingestion.preparation._price_parser import PriceParser


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("124,95 €", Decimal("124.95")),
        ("999,- €", Decimal("999.00")),
        ("9.999,- €", Decimal("9999.00")),
        ("1.299,99 €", Decimal("1299.99")),
        ("7,- €", Decimal("7.00")),
    ],
)
def test_parses_german_price_formats(raw, value):
    price = PriceParser.parse(raw)
    assert price.value == value
    assert price.currency == "EUR"
    assert price.original_value is None


def test_parses_discounted_multiline_price():
    price = PriceParser.parse("Ersparnis: 20,- €\nStatt 159,95\n139,95 €")
    assert price.value == Decimal("139.95")
    assert price.original_value == Decimal("159.95")
    assert price.savings == Decimal("20.00")
    assert price.currency == "EUR"


def test_unparseable_price_is_none():
    price = PriceParser.parse("")
    assert price.value is None
    assert price.currency is None
