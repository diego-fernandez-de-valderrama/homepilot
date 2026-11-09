from smart_home_agent.answer_tags import PlainTextRenderer
from smart_home_agent.models import RichContent
from smart_home_agent.repositories.catalog._product_mapper import ProductMapper
from smart_home_agent.tools import ToolRegistry
from tests.fakes import FakeToolContext, fact, product, services_for
from tests.unit.test_tools import by_name

WHITE = product("33081816", title="Access Point", price=59.95, subtitle="Weiß, 10 x 10 cm", variant="Weiß")
ANTHRACITE = product("33081825", title="Access Point", price=64.95, subtitle="Anthrazit, 10 x 10 cm")


def test_own_variant_is_the_option_named_in_the_subtitle():
    own_variant = ProductMapper.own_variant
    assert own_variant("GU10, Dimmbar, RGBW, 350 lm, 4,8 W, Weiß", ["Chrom", "Schwarz", "Weiß"]) == "Weiß"
    assert own_variant("E27, RGBW, 1.055 lm, 11 W", ["470 lm", "806 lm", "1.055 lm", "55 lm"]) == "1.055 lm"
    assert own_variant("Länge: 5 m, RGBW", ["2 m", "5 m"]) == "5 m"
    assert own_variant("E27, Dimmbar, Warmweiß", ["A60", "G80"]) is None
    assert own_variant(None, ["Weiß"]) is None
    assert own_variant("Weiß", []) is None


def test_lists_name_the_version_and_inline_items_show_the_title():
    content = RichContent(products={WHITE.id: WHITE, ANTHRACITE.id: ANTHRACITE})
    assert content.titles() == {WHITE.id: "Access Point", ANTHRACITE.id: "Access Point"}
    assert content.names() == {WHITE.id: "Access Point (Weiß)", ANTHRACITE.id: "Access Point"}
    tag = f'<item id="{WHITE.id}"/>'
    # Inline, the model names the version in its own words; "(Title)" right after the tag is an echo.
    plain = PlainTextRenderer(content.titles(), content.names()).render(f"Take the {tag} (Access Point) in white.")
    assert plain == "Take the Access Point in white."
    listed = PlainTextRenderer(content.titles(), content.names()).render(f'<items ids="{WHITE.id},{ANTHRACITE.id}"/>')
    assert listed == "- Access Point (Weiß)\n- Access Point"


def test_get_product_lists_the_other_versions():
    other = product("other", title="Something else", facts=[fact("google_home")])
    tools = by_name(ToolRegistry(services_for([WHITE, ANTHRACITE, other])).build())
    result = tools["get_product"](WHITE.id, FakeToolContext())
    assert result["product"]["subtitle"] == "Weiß, 10 x 10 cm"
    assert [v["id"] for v in result["other_versions"]] == [ANTHRACITE.id]
    assert result["other_versions"][0]["subtitle"] == "Anthrazit, 10 x 10 cm"
    assert tools["get_product"]("other", FakeToolContext())["other_versions"] == []


def test_ui_shows_which_version_a_product_is():
    from smart_home_agent.ui.components import ItemChipHtml, ProductCardHtml

    card = ProductCardHtml.cards([WHITE])
    assert '<span class="hp-card__version">Weiß, 10 x 10 cm</span>' in card
    chip = ItemChipHtml.render(WHITE, WHITE.id)
    assert '<span class="hp-item__name">Access Point</span>' in chip  # the text names the version
    assert '<span class="hp-item__version">Weiß, 10 x 10 cm</span>' in chip  # hover card
    assert "hp-card__version" not in ProductCardHtml.cards([product("12345678")])  # no subtitle, no line


def test_blocks_name_the_version():
    from smart_home_agent.models import UpsellSuggestion
    from smart_home_agent.services import ProductComparer, RichContentService
    from smart_home_agent.ui.components import ComparisonHtml, CompatibilityHtml, UpgradeHtml

    head = ComparisonHtml.render(ProductComparer.compare([WHITE, ANTHRACITE]))
    assert '<span class="hp-compare__version">Weiß, 10 x 10 cm</span>' in head
    assert '<span class="hp-compare__version">Anthrazit, 10 x 10 cm</span>' in head
    compat = CompatibilityHtml.render(WHITE, RichContentService.product_compatibility(WHITE, [], None))
    assert '<span class="hp-compat__version">Weiß, 10 x 10 cm</span>' in compat
    upsell = UpsellSuggestion(
        product_id=ANTHRACITE.id,
        title=ANTHRACITE.title,
        price=64.95,
        base_product_id=WHITE.id,
        price_difference=5.0,
        upgrade_reasons=[],
    )
    assert UpgradeHtml.render(WHITE, ANTHRACITE, upsell).count("hp-upgrade__version") == 2


def test_cart_results_name_the_version():
    from smart_home_agent.models import CartItem
    from smart_home_agent.tools.cart._change_report import ChangeReport

    cart = services_for([WHITE, ANTHRACITE]).cart
    before = cart.view([])
    after = cart.view([CartItem(product_id=WHITE.id, quantity=1)])
    [line] = after.for_model()
    assert (line["title"], line["variant"], line["subtitle"]) == ("Access Point", "Weiß", "Weiß, 10 x 10 cm")
    [change] = ChangeReport.build("ok", "add", [WHITE.id], before, after)["changes"]
    assert (change["variant"], change["subtitle"]) == ("Weiß", "Weiß, 10 x 10 cm")


def test_a_change_awaiting_confirmation_names_the_product_from_the_catalog():
    from smart_home_agent.tools.cart._change_report import ChangeReport

    services = services_for([WHITE, ANTHRACITE])
    empty = services.cart.view([])  # nothing added yet: neither cart view knows the product
    [change] = ChangeReport.build("awaiting_confirmation", "add", [WHITE.id], empty, empty, catalog=services.catalog)[
        "changes"
    ]
    assert (change["title"], change["variant"]) == ("Access Point", "Weiß")
    [unknown] = ChangeReport.build(
        "awaiting_confirmation", "add", ["99999999"], empty, empty, catalog=services.catalog
    )["changes"]
    assert unknown["title"] is None
