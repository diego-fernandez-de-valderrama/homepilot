import streamlit as st

from smart_home_agent.config import get_settings
from smart_home_agent.ui.backend import CustomerDirectory
from smart_home_agent.ui.state import UiSession
from smart_home_agent.ui.views.customer_memory_dialog import CustomerMemoryDialog
from smart_home_agent.ui.views.customer_picker import CustomerPicker


class Sidebar:
    """The dark rail: developer and testing controls only (customer content lives in the customer panel)."""

    @staticmethod
    def render(busy: bool) -> bool:
        """Returns the developer toggle. The controls expose every stored customer, so `AGENT_UI_DEV_TOOLS=false`
        hides them in shared deployments."""
        debug = False
        with st.sidebar:
            st.html('<p class="hp-rail-brand"><span class="hp-rail-brand__mark"></span>HomePilot</p>')
            if get_settings().agent.ui_dev_tools:
                debug = Sidebar._dev_tools(busy)
            st.html('<p class="hp-rail-footer">Answers based on the HomePilot catalog · EN / DE</p>')
        return debug

    @staticmethod
    def _dev_tools(busy: bool) -> bool:
        st.html('<p class="hp-rail-label">Testing</p>')
        CustomerPicker.render(CustomerDirectory.customers(), busy)
        st.html('<p class="hp-rail-label">Developer</p>')
        debug = st.toggle(
            "Developer panel",
            key="hp-debug",
            help="Show language, tools, candidates and compatibility.",
            disabled=busy,
        )
        if debug and st.button("Stored data about me", icon=":material/person_search:", width="stretch", disabled=busy):
            CustomerMemoryDialog.show(UiSession.customer_id())
        return debug
