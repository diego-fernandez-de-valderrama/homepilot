from typing import Any, Protocol


class StateHolder(Protocol):
    """The part of ADK's ToolContext / CallbackContext that reads and writes the state (easy to fake in tests)."""

    @property
    def state(self) -> Any: ...
