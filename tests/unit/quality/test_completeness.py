from catalog_ingestion.domain.enums import CompletenessLevel
from catalog_ingestion.extraction.compatibility import extract_compatibility
from catalog_ingestion.quality.completeness import assess_completeness
from tests.conftest import BOSCH_CONTROLLER, SPARSE_MATTER, THOMSON_NO_DESCRIPTION, load_normalized


def _assess(product_id: str):
    product = load_normalized(product_id)
    return assess_completeness(product, extract_compatibility(product))


def test_sparse_product_needs_web():
    report = _assess(SPARSE_MATTER)
    assert report.level is CompletenessLevel.SPARSE
    assert report.needs_web
    assert set(report.reasons) >= {"missing_description", "missing_attributes"}


def test_rich_product_does_not_need_web():
    report = _assess(BOSCH_CONTROLLER)
    assert report.level is CompletenessLevel.RICH
    assert not report.needs_web
    assert report.score == 1.0


def test_missing_description_only_is_partial():
    report = _assess(THOMSON_NO_DESCRIPTION)
    assert report.level is CompletenessLevel.PARTIAL
    assert "missing_description" in report.reasons
    assert report.needs_web
