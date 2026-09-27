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


def test_aliases_with_trademark_signs_are_reachable():
    from catalog_ingestion.vocabulary.compatibility import _BY_ALIAS, TERMS, normalize_alias

    for term in TERMS:
        for alias in term.aliases:
            assert normalize_alias(alias) in _BY_ALIAS, alias


def test_no_surface_form_matches_another_concept_as_a_word():
    from catalog_ingestion.validation.evidence import mentions_any
    from catalog_ingestion.vocabulary.compatibility import TERMS, surface_forms

    for term in TERMS:
        for other in TERMS:
            if other.canonical == term.canonical:
                continue
            for alias in (*other.aliases, other.label):
                # Allowed only when the form is made of whole words of the other alias; this guards
                # against in-word matches such as "lan" inside "wlan".
                if mentions_any(alias, surface_forms(term.canonical)):
                    words = set(alias.casefold().replace("-", " ").split())
                    forms = {form.casefold() for form in surface_forms(term.canonical)}
                    assert any(set(form.split()) <= words for form in forms), (
                        f"{term.canonical} matches inside {other.canonical} alias {alias!r}"
                    )


def test_mentions_any_uses_whole_words():
    from catalog_ingestion.validation.evidence import mentions_any
    from catalog_ingestion.vocabulary.compatibility import surface_forms

    assert not mentions_any("Steuerung per WLAN", surface_forms("ethernet"))
    assert mentions_any("Anschluss per LAN-Kabel", surface_forms("ethernet"))
    assert not mentions_any("Radios", surface_forms("ios"))
    assert not mentions_any("mit matter Oberfläche", surface_forms("matter"))
    assert mentions_any("Über Matter kompatibel", surface_forms("matter"))
    assert not mentions_any("geringer Verbrauch", surface_forms("ring"))
