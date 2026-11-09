import pytest

from catalog_ingestion.enrichment.validation._mention_matcher import MentionMatcher
from catalog_ingestion.vocabulary import CategoryVocabulary, CompatibilityTerm, CompatibilityVocabulary, Dimension
from catalog_ingestion.vocabulary.compatibility_vocabulary import _BY_ALIAS


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
    term = CompatibilityVocabulary.lookup(raw)
    assert term is not None
    assert (term.canonical, term.dimension) == (canonical, dimension)


def _term(raw: str) -> CompatibilityTerm:
    term = CompatibilityVocabulary.lookup(raw)
    assert term is not None, raw
    return term


def test_non_equivalent_concepts_stay_separate():
    assert _term("Apple Siri").canonical != _term("Apple HomeKit").canonical
    assert _term("Google Assistant").canonical != _term("Google Home").canonical
    assert _term("Matter").dimension is not _term("WLAN").dimension


def test_unknown_values_have_no_canonical_mapping():
    assert CompatibilityVocabulary.lookup("Philips Hue ZigBee Dimmschalter") is None
    assert CompatibilityVocabulary.lookup("App") is None


def test_slugs_are_unique_and_brand_pages_unmapped():
    slugs = [slug for category in CategoryVocabulary.CATEGORIES for slug in category.slugs]
    assert len(slugs) == len(set(slugs))
    assert all(CategoryVocabulary.for_slug(slug) is None for slug in CategoryVocabulary.BRAND_PAGE_SLUGS)


def test_aliases_with_trademark_signs_are_reachable():

    for term in CompatibilityVocabulary.TERMS:
        for alias in term.aliases:
            assert CompatibilityVocabulary.normalize_alias(alias) in _BY_ALIAS, alias


def test_no_surface_form_matches_another_concept_as_a_word():

    for term in CompatibilityVocabulary.TERMS:
        for other in CompatibilityVocabulary.TERMS:
            if other.canonical == term.canonical:
                continue
            for alias in (*other.aliases, other.label):
                # Allowed only when the form is made of whole words of the other alias; this guards
                # against in-word matches such as "lan" inside "wlan".
                if MentionMatcher.mentions_any(alias, CompatibilityVocabulary.surface_forms(term.canonical)):
                    words = set(alias.casefold().replace("-", " ").split())
                    forms = {form.casefold() for form in CompatibilityVocabulary.surface_forms(term.canonical)}
                    assert any(set(form.split()) <= words for form in forms), (
                        f"{term.canonical} matches inside {other.canonical} alias {alias!r}"
                    )


def test_mentions_any_uses_whole_words():

    assert not MentionMatcher.mentions_any("Steuerung per WLAN", CompatibilityVocabulary.surface_forms("ethernet"))
    assert MentionMatcher.mentions_any("Anschluss per LAN-Kabel", CompatibilityVocabulary.surface_forms("ethernet"))
    assert not MentionMatcher.mentions_any("Radios", CompatibilityVocabulary.surface_forms("ios"))
    assert not MentionMatcher.mentions_any("mit matter Oberfläche", CompatibilityVocabulary.surface_forms("matter"))
    assert MentionMatcher.mentions_any("Über Matter kompatibel", CompatibilityVocabulary.surface_forms("matter"))
    assert not MentionMatcher.mentions_any("geringer Verbrauch", CompatibilityVocabulary.surface_forms("ring"))
