import logging
import time

import streamlit as st

from smart_home_agent.config import get_settings
from smart_home_agent.container import build_profile_store
from smart_home_agent.models import CustomerSummary
from smart_home_agent.services import ProfileService

logger = logging.getLogger(__name__)


class CustomerDirectory:
    """The customer memory for the testing controls (picker, stored-data dialog). Reads the memory only (no
    Gemini or Qdrant), so it works before the first message."""

    RETRY_SECONDS = 60.0
    _down_until = 0.0  # process-wide: after a failure, reruns skip the database for a while

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def service() -> ProfileService | None:
        """None when the memory is off. A short connect timeout: the picker is drawn on every rerun."""
        store = build_profile_store(get_settings(), connect_timeout=2)
        return ProfileService(store) if store is not None else None

    @staticmethod
    @st.cache_data(ttl=5, show_spinner=False)
    def customers() -> list[CustomerSummary] | None:
        """Customers with stored facts, most recently active first; None when the memory is off or unreachable.
        Cached for a few seconds, so reruns (every click) do not query the database each time; after a failure the
        database is not asked again for a minute, so an unreachable memory never stalls every interaction."""
        directory = CustomerDirectory.service()
        if directory is None or time.monotonic() < CustomerDirectory._down_until:
            return None
        try:
            return directory.customers()
        except Exception:
            logger.warning("customer memory: listing the customers failed", exc_info=True)
            CustomerDirectory._down_until = time.monotonic() + CustomerDirectory.RETRY_SECONDS
            return None

    @staticmethod
    def refresh() -> None:
        """A turn may have stored facts: the next picker shows fresh counts."""
        CustomerDirectory.customers.clear()
