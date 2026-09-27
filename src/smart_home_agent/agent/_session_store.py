import asyncio
from typing import Any

from google.adk.events import Event
from google.adk.sessions import InMemorySessionService, Session

from smart_home_agent.session import SessionState, read_state


class SessionStore:
    """The in-memory ADK sessions of the app (they live as long as the process), plus one lock per session.

    One turn or cart edit at a time per session: each writes the whole SessionState, so interleaving (a Streamlit
    rerun starting a new turn, a cart edit during a turn) would lose updates.
    """

    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        self.service = InMemorySessionService()
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def lock(self, session_id: str, user_id: str) -> asyncio.Lock:
        """Created on the agent loop (callers are coroutines running there), so no extra locking is needed."""
        return self._locks.setdefault((user_id, session_id), asyncio.Lock())

    async def get(self, session_id: str, user_id: str) -> Session | None:
        return await self.service.get_session(app_name=self.app_name, user_id=user_id, session_id=session_id)

    async def get_or_create(self, session_id: str, user_id: str) -> Session:
        session = await self.get(session_id, user_id)
        if session is None:
            session = await self.service.create_session(app_name=self.app_name, user_id=user_id, session_id=session_id)
        return session

    async def raw_state(self, session_id: str, user_id: str) -> dict[str, Any]:
        """The whole ADK state of the session (empty when it does not exist yet)."""
        session = await self.get(session_id, user_id)
        return dict(session.state) if session else {}

    async def session_state(self, session_id: str, user_id: str) -> SessionState:
        return read_state(await self.raw_state(session_id, user_id))

    async def append_event(self, session: Session, event: Event) -> None:
        await self.service.append_event(session, event)
