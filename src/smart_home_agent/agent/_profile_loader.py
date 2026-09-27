import asyncio
import logging
from typing import Any

from smart_home_agent.models.profile import CustomerProfile
from smart_home_agent.services.profile import ProfileService

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Reads the customer memory for the agent; without a ProfileService the memory is disabled."""

    def __init__(self, profiles: ProfileService | None) -> None:
        self._profiles = profiles

    @property
    def enabled(self) -> bool:
        return self._profiles is not None

    async def snapshot(self, user_id: str) -> dict[str, Any] | None:
        """The profile as JSON for the session state, or None when there is no memory or loading failed."""
        profiles = self._profiles
        if profiles is None:
            return None
        try:
            profile = await asyncio.to_thread(profiles.profile, user_id, True)  # retracted: "no longer ..."
            return profile.model_dump(mode="json")
        except Exception:  # fail open: the turn runs with the previous snapshot, if any
            logger.warning("customer memory: loading the profile of %r failed", user_id, exc_info=True)
            return None

    def profile(self, user_id: str, include_retracted: bool) -> CustomerProfile | None:
        """Everything stored about the customer, live from the memory database (None without memory)."""
        if self._profiles is None:
            return None
        return self._profiles.profile(user_id, include_retracted)
