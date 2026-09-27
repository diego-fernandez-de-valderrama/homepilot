import dataclasses
from datetime import UTC, datetime

from catalog_ingestion.domain.enrichment import CompatibilityClaim, RequirementClaim, Spec, WebPage
from catalog_ingestion.domain.enums import (
    Dimension,
    FactSource,
    FactStatus,
    Method,
    Necessity,
    RequirementKind,
    WebStatus,
)
from catalog_ingestion.extraction.compatibility import extract_compatibility
from catalog_ingestion.extraction.requirements import extract_requirements
from catalog_ingestion.quality.completeness import assess_completeness
from catalog_ingestion.validation.evidence import quote_found
from catalog_ingestion.validation.validator import Validator
from tests.conftest import BOSCH_CONTROLLER, HUE_BRIDGE, SPARSE_MATTER, load_normalized
from tests.fakes import empty_llm


def _validate(product_id: str, llm=None, web_page=None):
    product = load_normalized(product_id)
    facts = extract_compatibility(product)
    return Validator().validate(
        product=product,
        completeness=assess_completeness(product, facts),
        facts=facts,
        requirements=extract_requirements(product),
        web_status=WebStatus.NOT_NEEDED,
        web_page=web_page,
        llm=llm,
        enrichment_model="fake" if llm else None,
        prompt_version="test" if llm else None,
    )


def _claim(value, quote, dimension=Dimension.ECOSYSTEM, status=FactStatus.SUPPORTED, source=FactSource.CATALOG):
    return CompatibilityClaim(dimension, value, status, source, quote)


WEB_PAGE = WebPage(
    url="https://www.bauhaus.info/x/p/32391327",
    ok=True,
    method="http",
    http_status=200,
    text="Fensterkontakt II [+M]. Über Matter kompatibel mit Apple Home und Google Home. Funk 868 MHz.",
    error=None,
    fetched_at=datetime(2026, 9, 26, tzinfo=UTC),
)


def test_web_claim_with_verbatim_evidence_is_accepted_with_provenance():
    claim = _claim("Apple Home", "Über Matter kompatibel mit Apple Home", source=FactSource.WEB)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), web_page=WEB_PAGE)
    fact = next(f for f in enriched.compatibility if f.canonical_value == "apple_home")
    assert fact.method is Method.LLM
    assert fact.evidence.source is FactSource.WEB
    assert fact.evidence.url == WEB_PAGE.url
    assert fact.confidence == 0.8


def test_claim_citing_the_wrong_source_is_reattributed():
    claim = _claim("Google Home", "kompatibel mit Apple Home und Google Home", source=FactSource.CATALOG)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), web_page=WEB_PAGE)
    fact = next(f for f in enriched.compatibility if f.canonical_value == "google_home")
    assert fact.evidence.source is FactSource.WEB


def test_hallucinated_evidence_is_dropped():
    claim = _claim("Apple HomeKit", "Funktioniert mit Apple HomeKit")
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)))
    assert "apple_home" not in {f.canonical_value for f in enriched.compatibility}
    assert any("evidence quote not found" in note for note in enriched.validation_notes)


def test_evidence_must_mention_the_claimed_value():
    # Real quote, but it talks about Siri, not HomeKit: Siri must not become HomeKit.
    quote = "Unterstützte Sprachsteuerung: Google Assistant, Amazon Alexa, Apple Siri"
    claim = _claim("Google Home", quote)
    enriched = _validate(BOSCH_CONTROLLER, empty_llm(compatibility_claims=(claim,)))
    assert "google_home" not in {f.canonical_value for f in enriched.compatibility}
    assert any("does not mention Google Home" in note for note in enriched.validation_notes)


def test_catalog_fact_wins_over_conflicting_llm_claim():
    quote = "Unterstützte Sprachsteuerung: Google Assistant, Amazon Alexa, Apple Siri"
    claim = _claim("Amazon Alexa", quote, dimension=Dimension.VOICE_ASSISTANT, status=FactStatus.UNSUPPORTED)
    enriched = _validate(BOSCH_CONTROLLER, empty_llm(compatibility_claims=(claim,)))
    alexa = [f for f in enriched.compatibility if f.canonical_value == "amazon_alexa"]
    assert len(alexa) == 1
    assert alexa[0].status is FactStatus.SUPPORTED and alexa[0].method is Method.DETERMINISTIC
    # The quote has no negation, so the "unsupported" claim is already dropped before the merge.
    assert any("explicit negative evidence" in note for note in enriched.validation_notes)


def test_wrong_dimension_is_reassigned_by_vocabulary():
    quote = "Unterstützte Sprachsteuerung: Google Assistant, Amazon Alexa, Apple Siri"
    claim = _claim("Apple Siri", quote, dimension=Dimension.ECOSYSTEM)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)))
    # The quote is not in the sparse product's sources, so it is dropped entirely.
    assert all(f.canonical_value != "apple_siri" for f in enriched.compatibility)


def _requirement(quote: str) -> RequirementClaim:
    return RequirementClaim("Philips Hue Bridge", RequirementKind.HUB, Necessity.REQUIRED, (), FactSource.WEB, quote)


def test_requirement_claim_needs_matching_evidence():
    page = dataclasses.replace(
        WEB_PAGE, text="Hinweis: Philips Hue Bridge erforderlich. Steuerung per Philips Hue App."
    )
    accepted = _validate(
        SPARSE_MATTER, empty_llm(requirement_claims=(_requirement("Philips Hue Bridge erforderlich"),)), web_page=page
    )
    requirement = next(r for r in accepted.requirements if r.canonical_item == "philips_hue_bridge")
    assert requirement.method is Method.LLM and requirement.evidence.source is FactSource.WEB

    # The quote exists but does not mention the bridge: rejected.
    rejected = _validate(SPARSE_MATTER, empty_llm(requirement_claims=(_requirement("Philips Hue App"),)), web_page=page)
    assert rejected.requirements == ()


def test_specs_must_appear_in_sources():
    specs = (Spec("Max devices", "50", None), Spec("Range", "300 m", "m"))
    enriched = _validate(HUE_BRIDGE, empty_llm(specs=specs))
    assert [s.name for s in enriched.specs] == ["Max devices"]


def test_llm_brand_must_be_in_title_and_category_only_fills_gaps():
    enriched = _validate(SPARSE_MATTER, empty_llm(brand="Siemens", category="security_camera"))
    assert enriched.brand == "Bosch"  # deterministic brand wins
    assert enriched.category == "contact_sensor"  # URL slug wins


def test_without_llm_only_deterministic_data_and_unknowns():
    enriched = _validate(SPARSE_MATTER)
    assert enriched.summary_en is None and enriched.use_cases == ()
    assert enriched.supported(Dimension.ECOSYSTEM) == ("matter",)
    assert enriched.supported(Dimension.PROTOCOL) == ()  # unknown, not "unsupported"
    assert enriched.enrichment_model is None


def test_quote_matching_is_whitespace_and_case_insensitive():
    assert quote_found("Amazon   ALEXA", "unterstützte sprachsteuerung: amazon alexa")
    assert quote_found("Amazon Alexa ... Apple Siri", "amazon alexa, google, apple siri")
    assert not quote_found("ab", "ab")  # too short to be evidence


def _hub_claim(item: str, quote: str, alternatives: tuple[str, ...] = ()) -> RequirementClaim:
    return RequirementClaim(item, RequirementKind.HUB, Necessity.REQUIRED, alternatives, FactSource.WEB, quote)


def _with_page(text: str, method: str = "http") -> WebPage:
    return dataclasses.replace(WEB_PAGE, text=text, method=method)


def test_negated_hub_requirements_are_rejected():
    cases = [
        ("Funktioniert ganz ohne Gateway (Hub) direkt per WLAN.", "Gateway", "Gateway (Hub)"),
        ("Kein HUB erforderlich. Einfach einschalten.", "Hub", "HUB erforderlich"),
        ("Keine zusätzliche Bridge erforderlich.", "Bridge", "Bridge erforderlich"),
        ("Works without a hub, straight over Wi-Fi.", "Hub", "a hub"),
    ]
    for text, item, quote in cases:
        enriched = _validate(SPARSE_MATTER, empty_llm(requirement_claims=(_hub_claim(item, quote),)), _with_page(text))
        assert all(r.method is not Method.LLM for r in enriched.requirements), text
        assert any("negates" in note for note in enriched.validation_notes), text


def test_negation_in_an_earlier_sentence_does_not_leak():
    text = "Nicht im Lieferumfang enthalten: Batterien. Philips Hue Bridge erforderlich."
    enriched = _validate(
        SPARSE_MATTER,
        empty_llm(requirement_claims=(_requirement("Philips Hue Bridge erforderlich"),)),
        _with_page(text),
    )
    assert any(r.canonical_item == "philips_hue_bridge" for r in enriched.requirements)


def test_negated_supported_claim_is_rejected_and_unsupported_needs_negation():
    page = _with_page("Dieses Gerät ist nicht kompatibel mit Apple HomeKit. Funk 868 MHz.")
    supported = _claim("Apple HomeKit", "kompatibel mit Apple HomeKit", source=FactSource.WEB)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(supported,)), page)
    assert all(f.canonical_value != "apple_home" for f in enriched.compatibility)

    unsupported = _claim(
        "Apple HomeKit", "nicht kompatibel mit Apple HomeKit", status=FactStatus.UNSUPPORTED, source=FactSource.WEB
    )
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(unsupported,)), page)
    fact = next(f for f in enriched.compatibility if f.canonical_value == "apple_home")
    assert fact.status is FactStatus.UNSUPPORTED

    bare = _claim("Matter", "Über Matter kompatibel", status=FactStatus.UNSUPPORTED, source=FactSource.WEB)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(bare,)), web_page=WEB_PAGE)
    assert all(f.status is not FactStatus.UNSUPPORTED for f in enriched.compatibility)


def test_requirement_alternatives_must_be_named_in_the_evidence():
    page = _with_page("Philips Hue Bridge erforderlich. Steuerung per App.")
    claim = _hub_claim("Philips Hue Bridge", "Philips Hue Bridge erforderlich", ("standalone", "Amazon Echo"))
    enriched = _validate(SPARSE_MATTER, empty_llm(requirement_claims=(claim,)), page)
    requirement = next(r for r in enriched.requirements if r.canonical_item == "philips_hue_bridge")
    assert requirement.alternatives == ("philips_hue_bridge",)
    assert any("dropped alternatives" in note for note in enriched.validation_notes)

    page = _with_page("Homematic IP Access Point oder Zentrale CCU3 notwendig.")
    claim = _hub_claim("Access Point", "Homematic IP Access Point", ("CCU3",))
    enriched = _validate(SPARSE_MATTER, empty_llm(requirement_claims=(claim,)), page)
    requirement = next(r for r in enriched.requirements if r.canonical_item == "homematic_ip_access_point")
    assert requirement.alternatives == ("homematic_ip_access_point", "homematic_ccu3")


def test_substring_matches_do_not_cross_concepts():
    page = _with_page("Steuerung per WLAN. Langlebige Batterie, geringer Stromverbrauch, Radios. Matter Lack.")
    claims = (
        _claim("LAN", "Steuerung per WLAN", dimension=Dimension.PROTOCOL, source=FactSource.WEB),
        _claim("Ring", "geringer Stromverbrauch", source=FactSource.WEB),
        _claim("iOS", "Radios", dimension=Dimension.MOBILE_OS, source=FactSource.WEB),
    )
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=claims), page)
    assert {f.canonical_value for f in enriched.compatibility if f.method is Method.LLM} == set()


def test_url_context_web_evidence_is_tagged_with_lower_confidence():
    claim = _claim("Apple Home", "Über Matter kompatibel mit Apple Home", source=FactSource.WEB)
    generated = dataclasses.replace(WEB_PAGE, method="gemini_url_context")
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), web_page=generated)
    fact = next(f for f in enriched.compatibility if f.canonical_value == "apple_home")
    assert fact.evidence.field == "web_page:url_context"
    assert fact.confidence == 0.6

    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), web_page=WEB_PAGE)
    fact = next(f for f in enriched.compatibility if f.canonical_value == "apple_home")
    assert (fact.evidence.field, fact.confidence) == ("web_page", 0.8)


def test_spec_numbers_must_match_whole_numbers_and_units():
    page = _with_page("Funkfrequenz 2,4 GHz. Reichweite 30 m.")
    specs = (
        Spec("Battery life", "2 years", None),
        Spec("Range", "4", "m"),
        Spec("Frequency", "2,4", "GHz"),
        Spec("Range", "30", "m"),
    )
    enriched = _validate(SPARSE_MATTER, empty_llm(specs=specs), page)
    assert [(s.name, s.value) for s in enriched.specs] == [("Frequency", "2,4"), ("Range", "30")]


def test_negation_is_scoped_to_the_claimed_term():
    kept = [
        (
            "Hinweise: Für manche Funktionen kann ein Abonnement bei Ring (nicht enthalten) notwendig sein.",
            RequirementClaim(
                "Abonnement bei Ring",
                RequirementKind.SUBSCRIPTION,
                Necessity.REQUIRED_FOR_SOME_FEATURES,
                (),
                FactSource.WEB,
                "Für manche Funktionen kann ein Abonnement bei Ring (nicht enthalten) notwendig sein",
            ),
        ),
        (
            "Die Datenübertragung erfolgt über das heimische WLAN-Netz, wodurch kein weiterer Hub nötig ist.",
            RequirementClaim(
                "WLAN-Netz",
                RequirementKind.NETWORK,
                Necessity.REQUIRED,
                (),
                FactSource.WEB,
                "Die Datenübertragung erfolgt über das heimische WLAN-Netz",
            ),
        ),
        (
            "Die Kamera lässt sich ohne Hub in Ihr WLAN-Netzwerk integrieren.",
            RequirementClaim(
                "WLAN-Netzwerk",
                RequirementKind.NETWORK,
                Necessity.REQUIRED,
                (),
                FactSource.WEB,
                "ohne Hub in Ihr WLAN-Netzwerk integrieren",
            ),
        ),
    ]
    for text, claim in kept:
        enriched = _validate(SPARSE_MATTER, empty_llm(requirement_claims=(claim,)), _with_page(text))
        assert any(r.method is Method.LLM for r in enriched.requirements), text


def test_negation_does_not_leak_across_attribute_lines():
    page = _with_page("Hub: nicht erforderlich\nProtokoll: Zigbee\nNotruf: Not- und Gefahrenfunktion")
    claim = _claim("Zigbee", "Protokoll: Zigbee", dimension=Dimension.PROTOCOL, source=FactSource.WEB)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), page)
    assert any(f.canonical_value == "zigbee" and f.method is Method.LLM for f in enriched.compatibility)


def test_lowercase_matter_in_titles_counts_but_the_adjective_does_not():
    from catalog_ingestion.validation.evidence import mentions_any
    from catalog_ingestion.vocabulary.compatibility import surface_forms

    forms = surface_forms("matter")
    assert mentions_any("Philips Hue Smart-LED-Lampe White 1100 matter", forms)
    assert mentions_any("für jede matterkompatible App geeignet", forms)
    assert mentions_any("Über Matter kompatibel", forms)
    assert not mentions_any("Gehäuse mit matter Oberfläche", forms)


def test_unsupported_accepts_a_negation_anywhere_earlier_in_the_clause():
    page = _with_page("Hinweis: Nicht mehr kompatibel mit der Zentrale CCU2.")
    claim = _claim("CCU2", "Nicht mehr kompatibel mit der Zentrale CCU2", status=FactStatus.UNSUPPORTED)
    claim = dataclasses.replace(claim, source=FactSource.WEB)
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), page)
    assert any(f.raw_value == "CCU2" and f.status is FactStatus.UNSUPPORTED for f in enriched.compatibility)


def test_unsupported_value_spanning_clauses_is_kept():
    page = _with_page("Hinweis: Nicht kompatibel mit der Stick Up Cam (1. Generation).")
    claim = _claim(
        "Stick Up Cam (1. Generation)",
        "Nicht kompatibel mit der Stick Up Cam (1. Generation).",
        status=FactStatus.UNSUPPORTED,
        source=FactSource.WEB,
    )
    enriched = _validate(SPARSE_MATTER, empty_llm(compatibility_claims=(claim,)), page)
    assert any(f.status is FactStatus.UNSUPPORTED for f in enriched.compatibility)
