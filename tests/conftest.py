import os
from collections.abc import Iterator
from typing import Any, cast

import pytest

from smart_home_agent.config import AgentSettings, get_settings


@pytest.fixture(autouse=True, scope="session")
def _default_agent_settings() -> Iterator[None]:
    """Unit tests see the documented defaults, never the developer's `.env` or shell (e.g. a local
    AGENT_GUARDRAIL_INPUT_OFF_TOPIC=true would change guardrail decisions); tests set what they need.
    Session-scoped, so module-scoped fixtures that build settings are isolated too."""
    with pytest.MonkeyPatch.context() as patch:
        for name in [n for n in os.environ if n.startswith("AGENT_")]:
            patch.delenv(name)
        patch.setitem(cast(dict[str, Any], AgentSettings.model_config), "env_file", None)
        yield


@pytest.fixture(autouse=True)
def _no_cached_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
