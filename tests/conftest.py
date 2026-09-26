import pytest

from smart_home_agent.config import get_settings


@pytest.fixture(autouse=True)
def _no_cached_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
