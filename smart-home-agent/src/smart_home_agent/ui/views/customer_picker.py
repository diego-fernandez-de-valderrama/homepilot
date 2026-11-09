import streamlit as st

from smart_home_agent.models import CustomerSummary
from smart_home_agent.ui.state import UiSession


class CustomerPicker:
    """Testing aid: pick a stored customer instead of remembering ids. Switching starts a new conversation."""

    NEW_CUSTOMER = "__new_customer__"  # picker option that asks for a new customer id

    @staticmethod
    def render(stored: list[CustomerSummary] | None, busy: bool) -> None:
        options = CustomerPicker.options(stored, UiSession.customer_id(), UiSession.known_customers())
        st.session_state["hp-customer-options"] = options  # for on_pick: values outside it are stale
        if st.session_state.get("hp-customer-pick") not in options:
            st.session_state["hp-customer-pick"] = UiSession.customer_id()
        st.selectbox(
            "Customer",
            options,
            key="hp-customer-pick",
            format_func=CustomerPicker.label,
            on_change=CustomerPicker.on_pick,
            disabled=busy,
            help="Each customer has their own memory. Switching starts a new conversation with that customer.",
        )
        if st.session_state["hp-customer-pick"] == CustomerPicker.NEW_CUSTOMER:
            st.text_input(
                "New customer id",
                key="hp-customer-new",
                placeholder="e.g. anna, then press Enter",
                on_change=CustomerPicker.on_create,
                disabled=busy,
            )
        else:
            st.caption(CustomerPicker.caption(UiSession.customer_id(), stored))

    @staticmethod
    def on_pick() -> None:
        choice = st.session_state["hp-customer-pick"]
        if choice not in st.session_state.get("hp-customer-options", []):
            # Not an option of the picker as drawn: the browser sent a stale value (it keeps a selectbox's value as
            # the displayed text). Never treat it as a customer id: keep the current customer.
            st.session_state["hp-customer-pick"] = UiSession.customer_id()
            return
        if choice != CustomerPicker.NEW_CUSTOMER:  # "New customer..." only reveals the id field
            UiSession.switch_customer(choice)

    @staticmethod
    def on_create() -> None:
        """The id typed for a new customer (Enter): it is selected at once, before anything is stored for it."""
        customer = st.session_state["hp-customer-new"].strip()
        st.session_state["hp-customer-new"] = ""
        new = CustomerPicker.NEW_CUSTOMER
        if not customer or customer in (new, CustomerPicker.label(new)):  # labels must stay unique
            return
        st.session_state["hp-customer-pick"] = customer
        UiSession.switch_customer(customer)

    @staticmethod
    def options(stored: list[CustomerSummary] | None, current: str, known: list[str]) -> list[str]:
        """Stored customers first (most recent first), then this session's other customers in the order they were
        used, then "New customer...". The order stays stable while switching."""
        ids = [c.user_id for c in stored or []]
        ids += [c for c in dict.fromkeys([*known, current]) if c not in ids]
        return [*ids, CustomerPicker.NEW_CUSTOMER]

    @staticmethod
    def label(option: str) -> str:
        """The displayed text of a picker option. It must never change for the same customer: Streamlit's browser
        side keeps the selection as this text, so a changing label (e.g. with a fact count) is sent back as an
        unknown value on the next interaction."""
        return "+ New customer…" if option == CustomerPicker.NEW_CUSTOMER else option

    @staticmethod
    def caption(customer: str, stored: list[CustomerSummary] | None) -> str:
        """What is stored for the selected customer (shown under the picker, never in the option labels)."""
        if stored is None:
            return "Stored customers are not available (customer memory off or not reachable)."
        summary = next((c for c in stored if c.user_id == customer), None)
        if summary is None or summary.active_facts == 0:
            return "Nothing stored for this customer yet."
        return f"{summary.active_facts} fact{'s' if summary.active_facts != 1 else ''} stored for this customer."
