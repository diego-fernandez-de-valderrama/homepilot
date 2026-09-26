import pytest

from catalog_ingestion.domain.enums import Dimension
from catalog_ingestion.vocabulary.categories import BRAND_PAGE_SLUGS, CATEGORIES, category_for_slug
from catalog_ingestion.vocabulary.compatibility import CompatibilityTerm, lookup


@pytest.mark.parametrize(
    ("raw", "canonical", "dimension"),
    [
        ("Apple HomeKit System", "apple_home", Dimension.ECOSYSTEM),
        ("Apple Siri", "apple_siri", Dimension.VOICE_ASSISTANT),
        ("Google Assistant", "google_assistant", Dimension.VOICE_ASSISTANT),
        ("Google Home", "google_home", Dimension.ECOSYSTEM),
        ("Matter", "matter", Dimension.ECOSYSTEM),
        ("WLAN", "wifi", Dimension.PROTOCOL),
        ("ZigBee 3.0", "zigbee", Dimension.PROTOCOL),
        ("Z-Wave Plus", "z_wave", Dimension.PROTOCOL),
        ("Thread", "thread", Dimension.PROTOCOL),
        ("Samsung Smart Things System", "samsung_smartthings", Dimension.ECOSYSTEM),
        ("iOS 8.0 oder höher", "ios", Dimension.MOBILE_OS),
        ("Amazon Echo Dot + App", "amazon_alexa", Dimension.VOICE_ASSISTANT),
    ],
)
def test_canonical_lookup(raw, canonical, dimension):
    term = lookup(raw)
    assert term is not None
    assert (term.canonical, term.dimension) == (canonical, dimension)


def _term(raw: str) -> CompatibilityTerm:
    term = lookup(raw)
    assert term is not None, raw
    return term


def test_non_equivalent_concepts_stay_separate():
    assert _term("Apple Siri").canonical != _term("Apple HomeKit").canonical
    assert _term("Google Assistant").canonical != _term("Google Home").canonical
    assert _term("Matter").dimension is not _term("WLAN").dimension


def test_unknown_values_have_no_canonical_mapping():
    assert lookup("Philips Hue ZigBee Dimmschalter") is None
    assert lookup("App") is None


def test_slugs_are_unique_and_brand_pages_unmapped():
    slugs = [slug for category in CATEGORIES for slug in category.slugs]
    assert len(slugs) == len(set(slugs))
    assert all(category_for_slug(slug) is None for slug in BRAND_PAGE_SLUGS)
