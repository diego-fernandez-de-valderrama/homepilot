"""Answer tags: parsing, plain-text fallback and resolution to catalog data (no model, in-memory catalog)."""

from catalog_ingestion.domain.enums import FactStatus

from smart_home_agent.agent.orchestrator import AgentService, build_agent
from smart_home_agent.models import rich
from smart_home_agent.models.recommendation import UpsellSuggestion
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
    segments = rich.parse(ANSWER)
    assert segments == [
        rich.TextSegment(f'The <item id="{BASIC.id}"/> fits your budget.'),
        rich.ItemsBlock((BASIC.id, PRO.id)),
        rich.CompatibilityBlock(PRO.id),
        rich.UpgradeBlock(BASIC.id, PRO.id),
        rich.CompareBlock((BASIC.id, PRO.id)),
    ]
    assert rich.referenced_ids(segments) == [BASIC.id, PRO.id]


def test_unknown_tags_malformed_ids_and_code_blocks_stay_text():
    text = f'<b>hi</b> <items ids="tado-x"/> <item id="123"/>\n```\n<items ids="{BASIC.id}"/>\n```'
    segments = rich.parse(text)
    assert segments == [rich.TextSegment(text)]
    assert rich.referenced_ids(segments) == []
    assert rich.replace_items(f'```<item id="{BASIC.id}"/>```', lambda pid: "X") == f'```<item id="{BASIC.id}"/>```'


def test_to_plain_never_shows_raw_tags():
    plain = rich.to_plain(ANSWER, {BASIC.id: BASIC.title})
    assert "<" not in plain
    assert plain.startswith("The Acme Basic Thermostat fits your budget.")
    assert f"- {PRO.id}" in plain  # no title known: the id, never an invented name


def test_resolve_without_tags_makes_no_catalog_call():
    class NoCatalog:
        def get_products(self, product_ids):
            raise AssertionError("no catalog call expected")

    assert RichContentService(NoCatalog()).resolve("Hello! How can I help?") is None  # type: ignore[arg-type]


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
    assert content.upgrades[rich.upgrade_key(BASIC.id, PRO.id)] == UPSELL
    assert rich.compare_key((BASIC.id, PRO.id)) in content.comparisons


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
    assert resolver().resolve(reversed_pair, last_upsell=UPSELL).upgrades == {}  # type: ignore[union-attr]
    assert resolver().resolve(ANSWER).upgrades == {}  # type: ignore[union-attr]  # no upsell in the session


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
    segments = rich.parse(f'<items ids="{BASIC.id}"/>\nThe <item id="{PRO.id}"/> is pricier.')
    assert rich.block_ids(segments) == {BASIC.id}


def test_titles_echoed_next_to_their_own_tag_are_removed():
    titles = {BASIC.id: BASIC.title}
    tag = f'<item id="{BASIC.id}"/>'
    for echoed in (
        f"The {tag} {BASIC.title} fits.",
        f"The **{BASIC.title}** ({tag}) fits.",
        f"The {BASIC.title} {tag} fits.",
    ):
        assert rich.strip_echoed_titles(echoed, titles) == f"The {tag} fits."
    other = f"The {tag} is cheaper than the Acme Pro Thermostat."
    assert rich.strip_echoed_titles(other, titles) == other  # only the product's own title, only next to it
    assert rich.to_plain(f"The {tag} {BASIC.title} fits.", titles) == f"The {BASIC.title} fits."
