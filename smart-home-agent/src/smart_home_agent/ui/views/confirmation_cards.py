import streamlit as st

from smart_home_agent.models import CartConfirmation
from smart_home_agent.ui.backend import ImageAvailability
from smart_home_agent.ui.components import ConfirmationHtml
from smart_home_agent.ui.state import ConfirmationTracker


class ConfirmationCards:
    """One card per proposed cart change, with confirm/cancel buttons while it is open."""

    @staticmethod
    def render(confirmations: list[CartConfirmation], interactive: bool) -> None:
        """Nothing changes before the customer clicks: the tool only runs after the confirmation turn.

        Every state renders the same element slots (lead line, then per card: card + actions). When the
        customer decides, the lead and the buttons turn into empty slots instead of disappearing: otherwise the
        elements below would shift up during the confirmation turn and Streamlit would keep the previous run's
        card in the freed slot as a faded duplicate until the answer is done."""
        missing = ImageAvailability.missing_for(
            [line.product for c in confirmations for line in c.lines if line.product]
        )
        lead = st.empty()
        if interactive and any(ConfirmationTracker.state_of(c.request_id) is None for c in confirmations):
            lead.html(ConfirmationHtml.lead(len(confirmations)))
        for confirmation in confirmations:
            ConfirmationCards._card(confirmation, interactive, missing)

    @staticmethod
    def _card(confirmation: CartConfirmation, interactive: bool, missing: frozenset[str]) -> None:
        rid = confirmation.request_id
        state = ConfirmationTracker.state_of(rid)
        with st.container(key=f"hp-confirm-{rid}"):
            st.html(ConfirmationHtml.card(confirmation, state, missing))
            actions = st.empty()
            if state is None and interactive:
                with actions.container(horizontal=True, gap="small", key=f"hp-confirm-actions-{rid}"):
                    adding = confirmation.action == "add"
                    st.button(
                        ConfirmationHtml.button_label(confirmation),
                        icon=":material/add_shopping_cart:" if adding else ":material/remove_shopping_cart:",
                        key=f"hp-confirm-yes-{rid}",
                        type="primary",
                        on_click=ConfirmationTracker.decide,
                        args=(rid, True),
                    )
                    st.button(
                        "Cancel", key=f"hp-confirm-no-{rid}", on_click=ConfirmationTracker.decide, args=(rid, False)
                    )
