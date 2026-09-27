import streamlit as st

from smart_home_agent.models import MAX_QUANTITY, CartLine, CartView
from smart_home_agent.ui.backend import AgentBackend, ImageAvailability
from smart_home_agent.ui.components import CartHtml, SetupPanelHtml
from smart_home_agent.ui.state import UiSession


class CartPanel:
    """The customer panel on the right (pinned by CSS): the cart, then what the advisor knows about the setup.
    The customer can change quantities or remove lines; only the advisor adds products."""

    @staticmethod
    def render(cart: CartView, busy: bool) -> None:
        """`busy`: a turn runs in this script run, so edits wait until it is done."""
        if not UiSession.cart_open():
            return
        with st.container(key="hp-cart-panel"):
            with st.container(horizontal=True, vertical_alignment="center", key="hp-cart-panel-head"):
                st.html(CartHtml.header(cart))
                st.button(
                    "",
                    icon=":material/close:",
                    key="hp-cart-close",
                    help="Hide your cart",
                    on_click=UiSession.toggle_cart,
                    disabled=busy,
                )
            CartPanel._lines(cart, busy)
            st.html(SetupPanelHtml.render(UiSession.latest_state()))

    @staticmethod
    def _lines(view: CartView, busy: bool) -> None:
        missing = ImageAvailability.missing_for([line.product for line in view.lines if line.product])
        for line in view.lines:
            with st.container(key=f"hp-cart-line-{line.product_id}"):
                st.html(CartHtml.line(line, missing))
                CartPanel._stepper(line, busy)
        if view.lines:
            st.html(CartHtml.total(view))

    @staticmethod
    def _stepper(line: CartLine, busy: bool) -> None:
        pid = line.product_id
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"hp-cart-step-{pid}"):
            st.button(
                "",
                icon=":material/remove:",
                key=f"hp-cart-less-{pid}",
                help="One less",
                type="tertiary",
                disabled=busy,
                on_click=CartPanel._change_quantity,
                args=(pid, line.quantity - 1),
            )
            st.html(f'<span class="hp-cart__qty" aria-label="Quantity">{line.quantity}</span>')
            st.button(
                "",
                icon=":material/add:",
                key=f"hp-cart-more-{pid}",
                help="One more",
                type="tertiary",
                disabled=busy or not line.available or line.quantity >= MAX_QUANTITY,
                on_click=CartPanel._change_quantity,
                args=(pid, line.quantity + 1),
            )
            st.button(
                "",
                icon=":material/delete:",
                key=f"hp-cart-remove-{pid}",
                help="Remove from cart",
                type="tertiary",
                disabled=busy,
                on_click=CartPanel._change_quantity,
                args=(pid, 0),
            )

    @staticmethod
    def _change_quantity(product_id: str, quantity: int) -> None:
        AgentBackend.set_quantity(UiSession.session_id(), product_id, quantity, UiSession.customer_id())
