import logging
from functools import partial

import streamlit as st

from smart_home_agent.agent import AgentService, build_agent
from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models import CartView
from smart_home_agent.ui.backend.turn_starter import TurnStarter

logger = logging.getLogger(__name__)


class AgentBackend:
    """The UI's only door to the agent. Built lazily (the first message), cached per process, and every read
    fails soft: the page must survive backend failures and keep showing the conversation."""

    @staticmethod
    @st.cache_resource(show_spinner="Starting HomePilot...")
    def service() -> AgentService:
        settings = get_settings()
        container = build_container(settings)
        agent = build_agent(container.services, settings, container.guardrail)
        services = container.services
        return AgentService(agent, settings.agent.app_name, services.rich_content, services.cart, services.profile)

    @staticmethod
    def message_turn(session_id: str, prompt: str, customer_id: str) -> TurnStarter:
        return partial(AgentBackend.service().submit, session_id, prompt, customer_id)

    @staticmethod
    def confirmation_turn(session_id: str, decisions: dict[str, bool], customer_id: str) -> TurnStarter:
        return partial(AgentBackend.service().submit_confirmation, session_id, decisions, customer_id)

    @staticmethod
    def cart(session_id: str, customer_id: str) -> CartView:
        """Read live from the agent session (the customer can change it without a turn)."""
        try:
            return AgentBackend.service().cart(session_id, customer_id)
        except Exception:  # the UI must survive backend failures: the page still shows the conversation
            logger.exception("reading the cart failed")
            st.toast("The cart could not be loaded right now.", icon=":material/error:")
            return CartView()

    @staticmethod
    def set_quantity(session_id: str, product_id: str, quantity: int, customer_id: str) -> None:
        try:
            AgentBackend.service().set_cart_quantity(session_id, product_id, quantity, customer_id)
        except ValueError:  # the line changed in the meantime (for example removed by the advisor)
            st.toast("That product is no longer in your cart.", icon=":material/info:")

    @staticmethod
    def applied_confirmations(session_id: str, request_ids: list[str], customer_id: str) -> set[str]:
        try:
            return AgentBackend.service().applied_confirmations(session_id, request_ids, customer_id)
        except Exception:  # unknown: treat every change as applied rather than risk applying one twice
            logger.exception("reading the applied cart changes failed")
            return set(request_ids)
