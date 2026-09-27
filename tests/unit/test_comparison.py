import pytest
from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.models import NOT_LISTED, Spec
from smart_home_agent.services.comparison import ComparisonService, compare
from smart_home_agent.services.compatibility import ProductNotFoundError
from tests.fakes import FakeCatalog, fact, product, requirement


def _row(result, attribute):
    return next(r for r in result.rows if r.attribute == attribute)


A = product(
    "a",
    title="Thermo A",
    price=55.0,
    brand="Bosch",
    facts=[fact("apple_home"), fact("zigbee")],
    specs=[Spec(name="Battery type", value="AA")],
    requirements=[requirement("bosch_smart_home_controller")],
)
B = product(
    "b",
    title="Thermo B",
    price=69.95,
    brand="Bosch",
    facts=[fact("apple_home"), fact("matter", FactStatus.UNSUPPORTED)],
    specs=[Spec(name="Battery type", value="AAA"), Spec(name="Humidity", value="80", unit="%")],
)


def test_general_rows_use_structured_values():
    result = compare([A, B])
    assert _row(result, "price").values == ["55.00 EUR", "69.95 EUR"]
    assert _row(result, "price").differs
    assert _row(result, "brand").values == ["Bosch", "Bosch"]
    assert not _row(result, "brand").differs
    assert [p.id for p in result.products] == ["a", "b"]


def test_compatibility_rows_distinguish_supported_unsupported_and_unknown():
    result = compare([A, B])
    assert _row(result, "Apple Home (HomeKit)").values == ["supported", "supported"]
    assert _row(result, "Zigbee").values == ["supported", "unknown (not listed)"]
    assert _row(result, "Matter").values == ["unknown (not listed)", "unsupported"]


def test_missing_attributes_are_marked_not_listed():
    result = compare([A, B])
    assert _row(result, "Humidity").values == [NOT_LISTED, "80 %"]
    assert _row(result, "requirements").values[1] == NOT_LISTED
    assert "Bosch Smart Home Controller" in _row(result, "requirements").values[0]


def test_capability_differences():
    result = compare([A, B])
    assert result.only_supported_by == {"a": ["Zigbee"], "b": []}
    assert any("Lowest price: Thermo A" in note for note in result.notes)


def test_service_validates_input():
    service = ComparisonService(FakeCatalog([A, B]))
    with pytest.raises(ValueError):
        service.compare(["a"])
    with pytest.raises(ValueError):
        service.compare(["a", "a"])  # duplicates collapse to one product
    with pytest.raises(ProductNotFoundError):
        service.compare(["a", "404"])
    assert len(service.compare(["a", "b"]).products) == 2
