import pytest

from smart_home_agent.models.cart import MAX_QUANTITY, CartChange, CartItem
from smart_home_agent.services.cart import CartChangeError, CartService, NotInCartError, is_central_unit
from smart_home_agent.services.compatibility import ProductNotFoundError
from tests.fakes import FakeCatalog, product

CATALOG = FakeCatalog([product("a", price=10.0), product("b", price=2.5), product("free", price=None)])


@pytest.fixture
def cart() -> CartService:
    return CartService(CATALOG)


def items(*pairs: tuple[str, int]) -> list[CartItem]:
    return [CartItem(product_id=pid, quantity=q) for pid, q in pairs]


def pairs(cart_items: list[CartItem]) -> list[tuple[str, int]]:
    return [(i.product_id, i.quantity) for i in cart_items]


@pytest.mark.parametrize(
    ("product_type", "central"),
    [
        ("Smart home controller", True),  # Velux App Control KIG 300
        ("Starter Set", True),
        ("Smart home access point", True),
        ("WiFi bridge", True),
        ("Smart Home Control Center", True),
        ("Starter kit with gateway and climate sensors", True),
        ("RGBW LED Controller", False),  # per-room devices, not central units
        ("Underfloor heating controller", False),
        ("Wireless remote control", False),
        ("Roller blind motor", False),
        ("Smart LED bulb set", False),
    ],
)
def test_central_units_are_recognized_by_their_product_type(product_type, central):
    assert is_central_unit(product("x", product_type=product_type)) is central


def test_central_unit_by_title_when_the_type_is_missing():
    assert is_central_unit(product("x", title="Philips Hue Bridge", product_type=None))
    assert not is_central_unit(product("x", title="Hue White E27", product_type=None))


def test_central_units_over_one_counts_the_cart_too():
    catalog = FakeCatalog([product("hub", product_type="Smart home hub"), product("plug", product_type="Smart plug")])
    service = CartService(catalog)
    six = [CartChange(product_id="hub", quantity=6), CartChange(product_id="plug", quantity=6)]
    assert [(p.id, n) for p, n in service.central_units_over_one([], six)] == [("hub", 6)]
    one = [CartChange(product_id="hub", quantity=1)]
    assert service.central_units_over_one([], one) == []
    assert [(p.id, n) for p, n in service.central_units_over_one(items(("hub", 1)), one)] == [("hub", 2)]


def test_add_merges_lines_and_caps_the_quantity(cart):
    assert pairs(cart.add([], "a", 2)) == [("a", 2)]
    assert pairs(cart.add(items(("a", 2)), "a")) == [("a", 3)]
    assert pairs(cart.add(items(("a", MAX_QUANTITY - 1)), "a", 5)) == [("a", MAX_QUANTITY)]
    assert pairs(cart.add(items(("a", 1)), "b", 1)) == [("a", 1), ("b", 1)]


def test_add_rejects_unknown_products_and_bad_quantities(cart):
    with pytest.raises(ProductNotFoundError):
        cart.add([], "nope")
    with pytest.raises(ValueError):
        cart.add([], "a", 0)
    with pytest.raises(ValueError):
        cart.add([], "a", MAX_QUANTITY + 1)


def test_add_does_not_mutate_the_input(cart):
    original = items(("a", 1))
    cart.add(original, "a")
    assert pairs(original) == [("a", 1)]


def test_remove_partial_all_and_missing(cart):
    assert pairs(cart.remove(items(("a", 3), ("b", 1)), "a", 2)) == [("a", 1), ("b", 1)]
    assert pairs(cart.remove(items(("a", 3), ("b", 1)), "a")) == [("b", 1)]
    assert pairs(cart.remove(items(("a", 3)), "a", 10)) == []
    with pytest.raises(NotInCartError):
        cart.remove(items(("a", 1)), "b")


def test_set_quantity_zero_removes_the_line(cart):
    assert pairs(cart.set_quantity(items(("a", 3)), "a", 1)) == [("a", 1)]
    assert pairs(cart.set_quantity(items(("a", 3), ("b", 1)), "a", 0)) == [("b", 1)]
    with pytest.raises(NotInCartError):
        cart.set_quantity([], "a", 1)


def test_view_reads_prices_from_the_catalog(cart):
    view = cart.view(items(("a", 2), ("b", 3), ("gone", 1), ("free", 1)))
    assert view.item_count == 7
    assert view.total == 27.5  # the gone and the unpriced lines are not in the total
    assert view.has_unpriced
    gone = next(line for line in view.lines if line.product_id == "gone")
    assert not gone.available and gone.line_total is None
    assert view.quantity_of("b") == 3 and view.quantity_of("x") == 0
    assert cart.view([]).lines == [] and cart.view([]).total == 0.0


def test_changes_parse_and_merge(cart):
    assert [(c.product_id, c.quantity) for c in cart.changes("add", ["a", "b", "a"], [1, 2, 3])] == [
        ("a", 4),
        ("b", 2),
    ]
    assert [(c.product_id, c.quantity) for c in cart.changes("add", ["a"])] == [("a", 1)]
    assert [c.quantity for c in cart.changes("remove", ["a", "b"])] == [None, None]
    assert [c.quantity for c in cart.changes("remove", ["a", "b"], [2, 0])] == [2, None]
    assert [c.quantity for c in cart.changes("remove", ["a", "a"], [2, 0])] == [None]  # "all" wins
    for bad in (([], None), (["a"], [1, 2]), (["a"], [0]), (["a"], [MAX_QUANTITY + 1])):
        with pytest.raises(ValueError):
            cart.changes("add", *bad)


def test_apply_is_all_or_nothing(cart):
    start = items(("a", 1))
    assert pairs(cart.apply(start, "add", cart.changes("add", ["a", "b"], [1, 2]))) == [("a", 2), ("b", 2)]
    with pytest.raises(CartChangeError) as error:
        cart.apply(start, "add", cart.changes("add", ["b", "nope"]))
    assert error.value.status == "not_found" and [e["product_id"] for e in error.value.errors] == ["nope"]
    with pytest.raises(CartChangeError) as error:
        cart.apply(start, "remove", cart.changes("remove", ["a", "b"]))
    assert error.value.status == "invalid_input"
    assert pairs(start) == [("a", 1)]


def test_describe_a_pending_change(cart):
    change = cart.describe("r1", "remove", {"product_ids": ["a"]}, items(("a", 4)))
    [line] = change.lines
    assert (change.action, line.quantity, line.in_cart, line.units, change.after(line)) == ("remove", None, 4, 4, 0)
    assert line.product is not None and line.product.price == 10.0
    batch = cart.describe("r2", "add", {"product_ids": ["a", "b"], "quantities": [2, 1]}, items(("a", 1)))
    assert [(line.product_id, line.quantity, batch.after(line)) for line in batch.lines] == [("a", 2, 3), ("b", 1, 1)]
    assert batch.total == 22.5
    unknown = cart.describe("r3", "add", {"product_ids": ["zzz"], "quantities": [2]}, [])
    assert unknown.lines[0].product is None and unknown.total is None
    malformed = cart.describe("r4", "add", {"product_ids": ["a"], "quantities": [1, 2]}, [])
    assert [line.product_id for line in malformed.lines] == ["a"]  # still shown; the tool reports the error


def test_merged_removal_of_a_full_line_or_more_means_all_units(cart):
    [change] = cart.changes("remove", ["a", "a"], [60, 60])
    assert change.quantity is None
    [partial] = cart.changes("remove", ["a", "a"], [2, 3])
    assert partial.quantity == 5
