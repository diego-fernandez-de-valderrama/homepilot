"""Answer tags: parsing, plain-text fallback and resolution to catalog data (no model, in-memory catalog)."""

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.agent import AgentService, build_agent
from smart_home_agent.answer_tags import (
    CompareBlock,
    CompatibilityBlock,
    ItemsBlock,
    PlainTextRenderer,
    ProseRenderer,
    TagParser,
    TagSanitizer,
    TextSegment,
    UpgradeBlock,
)
from smart_home_agent.models import RichContent, UpsellSuggestion
from smart_home_agent.services.rich_content import RichContentService
from tests.fakes import FakeCatalog, fact, product, services_for
from tests.unit.test_guardrail_agent import ScriptedLlm, settings, text_response

BASIC = product("30000001", title="Acme Basic Thermostat", price=49.0, facts=[fact("google_home")])
PRO = product(
    "30000002",
    title="Acme Pro Thermostat",
    price=79.0,
    facts=[fact("google_home"), fact("apple_home", FactStatus.UNKNOWN), fact("matter")],
)
UPSELL = UpsellSuggestion(
    product_id=PRO.id,
    title=PRO.title,
    price=79.0,
    base_product_id=BASIC.id,
    price_difference=30.0,
    upgrade_reasons=["Also supports Matter"],
)
ANSWER = f"""The <item id="{BASIC.id}"/> fits your budget.

<items ids="{BASIC.id},{PRO.id}"/>

<compatibility id="{PRO.id}"/>
<upgrade from="{BASIC.id}" to="{PRO.id}"/>
<compare ids="{BASIC.id}, {PRO.id}"/>"""


def resolver() -> RichContentService:
    return RichContentService(FakeCatalog([BASIC, PRO]))


def test_parse_splits_blocks_and_keeps_inline_items_in_text():
    segments = TagParser.parse(ANSWER)
    assert segments == [
        TextSegment(f'The <item id="{BASIC.id}"/> fits your budget.'),
        ItemsBlock((BASIC.id, PRO.id)),
        CompatibilityBlock(PRO.id),
        UpgradeBlock(BASIC.id, PRO.id),
        CompareBlock((BASIC.id, PRO.id)),
    ]
    assert TagParser.referenced_ids(segments) == [BASIC.id, PRO.id]


def test_unknown_tags_malformed_ids_and_code_blocks_stay_text():
    text = f'<b>hi</b> <items ids="tado-x"/> <item id="123"/>\n```\n<items ids="{BASIC.id}"/>\n```'
    segments = TagParser.parse(text)
    assert segments == [TextSegment(text)]
    assert TagParser.referenced_ids(segments) == []
    assert (
        ProseRenderer.replace_items(f'```<item id="{BASIC.id}"/>```', lambda pid: "X")
        == f'```<item id="{BASIC.id}"/>```'
    )


def test_to_plain_never_shows_raw_tags():
    plain = PlainTextRenderer({BASIC.id: BASIC.title}).render(ANSWER)
    assert "<" not in plain
    assert plain.startswith("The Acme Basic Thermostat fits your budget.")
    assert f"- {PRO.id}" in plain  # no title known: the id, never an invented name


def test_resolve_without_tags_makes_no_catalog_call():
    class NoCatalog:
        def get_products(self, product_ids):
            raise AssertionError("no catalog call expected")

        def get_product(self, product_id):
            raise AssertionError("no catalog call expected")

        def filter_products(self, criteria):
            raise AssertionError("no catalog call expected")

        def get_versions(self, titles):
            raise AssertionError("no catalog call expected")

    assert RichContentService(NoCatalog()).resolve("Hello! How can I help?") is None


def test_resolve_against_setup_keeps_unknown_unknown():
    content = resolver().resolve(ANSWER, must_support=["google_home", "apple_home"], last_upsell=UPSELL)
    assert content is not None
    assert set(content.products) == {BASIC.id, PRO.id}
    compatibility = content.compatibility[PRO.id]
    assert compatibility.against_setup
    assert compatibility.result.overall is FactStatus.UNKNOWN
    assert {c.term: c.status for c in compatibility.result.checks} == {
        "google_home": FactStatus.SUPPORTED,
        "apple_home": FactStatus.UNKNOWN,
    }
    assert content.upgrades[RichContent.upgrade_key(BASIC.id, PRO.id)] == UPSELL
    assert RichContent.compare_key((BASIC.id, PRO.id)) in content.comparisons


def test_resolve_without_setup_shows_the_products_own_facts():
    content = resolver().resolve(f'<compatibility id="{PRO.id}"/>')
    assert content is not None
    compatibility = content.compatibility[PRO.id]
    assert not compatibility.against_setup
    assert {c.term: c.status for c in compatibility.result.checks} == {
        "google_home": FactStatus.SUPPORTED,
        "apple_home": FactStatus.UNKNOWN,
        "matter": FactStatus.SUPPORTED,
    }


def test_upgrade_only_for_the_recommenders_upsell():
    reversed_pair = f'<upgrade from="{PRO.id}" to="{BASIC.id}"/>'
    reversed_content = resolver().resolve(reversed_pair, last_upsell=UPSELL)
    assert reversed_content is not None and reversed_content.upgrades == {}
    content = resolver().resolve(ANSWER)
    assert content is not None and content.upgrades == {}  # no upsell in the session


def test_unknown_ids_get_no_data():
    content = resolver().resolve(f'<compatibility id="39999999"/>\n<compare ids="{BASIC.id},39999999"/>')
    assert content is not None
    assert set(content.products) == {BASIC.id}
    assert content.compatibility == {}
    assert content.comparisons == {}  # fewer than two known products


def test_agent_reply_carries_resolved_content():
    llm = ScriptedLlm(script=[text_response(f'The <item id="{BASIC.id}"/> fits.')])
    services = services_for([BASIC, PRO])
    agent = build_agent(services, settings(guardrail_output_check=False), model=llm)
    reply = AgentService(agent, "test-app", services.rich_content).chat("s1", "Thermostat for Google Home?")
    assert reply.rich is not None
    assert reply.rich.titles() == {BASIC.id: BASIC.title}


def test_block_ids_are_the_products_displayed_by_components():
    segments = TagParser.parse(f'<items ids="{BASIC.id}"/>\nThe <item id="{PRO.id}"/> is pricier.')
    assert TagParser.block_ids(segments) == {BASIC.id}


def test_titles_echoed_next_to_their_own_tag_are_removed():
    titles = {BASIC.id: BASIC.title}
    tag = f'<item id="{BASIC.id}"/>'
    for echoed in (
        f"The {tag} {BASIC.title} fits.",
        f"The **{BASIC.title}** ({tag}) fits.",
        f"The {BASIC.title} {tag} fits.",
        f"The {tag} ({BASIC.title}) fits.",
    ):
        assert ProseRenderer.strip_echoed_titles(echoed, titles) == f"The {tag} fits."
    partial = f"The {tag} ({BASIC.title} in anthracite) fits."
    assert ProseRenderer.strip_echoed_titles(partial, titles) == f"The {tag} (in anthracite) fits."
    other = f"The {tag} is cheaper than the Acme Pro Thermostat."
    assert ProseRenderer.strip_echoed_titles(other, titles) == other  # only the product's own title, only next to it
    assert PlainTextRenderer(titles).render(f"The {tag} {BASIC.title} fits.") == f"The {BASIC.title} fits."


def test_strip_invalid_tags_removes_what_would_never_render():
    text = (
        f'Add a <item id="philips_hue_bridge"/>. Then <item id="{BASIC.id}"/> works.\n'
        f'<items ids="hue-bridge"/>\n<compare ids="{BASIC.id}"/>\n<upgrade from="{PRO.id}" to="{BASIC.id}"/>\n'
        f"The <item>Hue Bridge</item> (<item id='x'>) is required <items ids=\"{BASIC.id}\""
    )
    assert TagSanitizer((BASIC.id, PRO.id)).strip_invalid(text) == (
        f'Add a. Then <item id="{BASIC.id}"/> works.\nThe Hue Bridge is required'
    )


def test_strip_invalid_tags_keeps_valid_tags_and_code():
    code = '```\n<item id="hue"/>\n```'
    assert TagSanitizer((BASIC.id, PRO.id)).strip_invalid(ANSWER) == ANSWER
    assert TagSanitizer().strip_invalid(code) == code
    assert TagSanitizer().strip_invalid(ANSWER) == ANSWER.replace(f'<upgrade from="{BASIC.id}" to="{PRO.id}"/>\n', "")


def test_invalid_tags_never_reach_the_interface_or_the_history():
    llm = ScriptedLlm(
        script=[text_response(f'You need a <item id="philips_hue_bridge"/> for <item id="{BASIC.id}"/>.')]
    )
    services = services_for([BASIC, PRO])
    agent = AgentService(build_agent(services, settings(), model=llm), "test-app", services.rich_content)
    reply = agent.chat("s1", "Thermostat for Google Home?")
    assert reply.text == f'You need a for <item id="{BASIC.id}"/>.'
    agent.chat("s1", "Thanks")
    history = llm.requests[-1].contents[-2]
    assert history.parts is not None and history.parts[0].text == reply.text


def test_answer_of_only_invalid_tags_is_replaced_by_the_fallback():
    llm = ScriptedLlm(script=[text_response('<items ids="hue_bridge"/>')])
    reply = AgentService(build_agent(services_for([BASIC]), settings(), model=llm), "test-app").chat("s1", "Hi")
    assert reply.text and "<" not in reply.text


def test_upgrade_attributes_in_either_order_are_kept():
    text = 'Better: <upgrade to="22222222" from="11111111"/>'
    assert TagSanitizer(("11111111", "22222222")).strip_invalid(text) == text
    assert TagParser.parse(text)[-1] == UpgradeBlock("11111111", "22222222")


def test_a_tag_split_over_lines_is_joined_not_left_as_raw_text():
    text = 'Options:\n<items ids="11111111,\n22222222"/>\nDone.'
    stripped = TagSanitizer().strip_invalid(text)
    assert '<items ids="11111111, 22222222"/>' in stripped
    assert ItemsBlock(("11111111", "22222222")) in TagParser.parse(text)


def test_echoed_title_keeps_the_parenthesis_of_the_surrounding_text():
    titles = {"11111111": "Acme Thermostat"}
    text = 'Two options (the Acme Thermostat <item id="11111111"/>) fit.'
    assert ProseRenderer.strip_echoed_titles(text, titles) == 'Two options (the <item id="11111111"/>) fit.'
    assert ProseRenderer.strip_echoed_titles('Acme Thermostat (<item id="11111111"/>) fits.', titles) == (
        '<item id="11111111"/> fits.'
    )
