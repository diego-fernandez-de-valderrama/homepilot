import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import Any


class EventLoopThread:
    """One long-lived event loop in a daemon thread that runs every turn.

    ADK caches its Gemini client per loop, so a new loop per turn (`asyncio.run`) would leave clients bound to
    closed loops.
    """

    def __init__(self, name: str) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name=name, daemon=True).start()

    def run[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        """Runs the coroutine on the loop and blocks until it is done."""
        return self.submit(coroutine).result()

    def submit[T](self, coroutine: Coroutine[Any, Any, T]) -> Future[T]:
        """Starts the coroutine on the loop without blocking."""
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)
