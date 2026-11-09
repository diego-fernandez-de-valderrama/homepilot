import streamlit as st

from smart_home_agent.models import CartView
from smart_home_agent.ui.components import ChromeHtml
from smart_home_agent.ui.state import UiSession


class Masthead:
    """Pinned masthead: the brand, "New conversation" and the cart button that opens the customer panel."""

    @staticmethod
    def render(cart: CartView, busy: bool) -> None:
        """`busy`: a turn runs in this script run; a click would rerun the script and cut it off."""
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key="hp-masthead"):
            st.html(ChromeHtml.masthead())
            if st.button("New conversation", icon=":material/refresh:", key="hp-new-conversation", disabled=busy):
                UiSession.reset_conversation()
                st.rerun()
            count = cart.item_count
            label = f"{count} item{'s' if count != 1 else ''} in your cart"
            st.button(
                str(count),
                icon=":material/shopping_cart:",
                key=f"hp-cart-toggle-{'filled' if count else 'empty'}",  # the key suffix drives the filled style
                help=f"{label}. Click to {'hide' if UiSession.cart_open() else 'show'} your cart.",
                on_click=UiSession.toggle_cart,
                disabled=busy,
            )
