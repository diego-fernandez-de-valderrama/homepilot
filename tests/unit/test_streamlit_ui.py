from pathlib import Path

from streamlit.testing.v1 import AppTest

from smart_home_agent.agent.state import SessionState
from smart_home_agent.ui import streamlit_app
from smart_home_agent.ui.components import Suggestion, setup_panel_html, suggestion_tile_html

APP = Path(streamlit_app.__file__)


def test_empty_state_renders_without_backend():
    app = AppTest.from_file(str(APP)).run()  # the agent service is only built when a prompt arrives
    assert not app.exception
    labels = [button.label for button in app.button]
    assert "New conversation" in labels
    assert all(s.title in labels for s in streamlit_app.SUGGESTIONS)
    assert [toggle.label for toggle in app.toggle] == ["Developer panel"]


def test_setup_panel_without_known_facts_invites_the_user():
    assert "Tell me about your setup" in setup_panel_html(None)
    assert "Tell me about your setup" in setup_panel_html(SessionState())


def test_setup_panel_shows_only_known_facts_with_labels():
    state = SessionState(language="de", user_ecosystems=["apple_home"], owned_devices=[], budget_max=150)
    panel = setup_panel_html(state)
    assert "Apple Home" in panel
    assert "up to 150 €" in panel
    assert "None" in panel  # the user said they own no hub
    assert "Deutsch" in panel
    assert "Looking at" not in panel


def test_dynamic_values_are_escaped():
    panel = setup_panel_html(SessionState(requirements=["<script>x</script>"]))
    assert "<script>" not in panel
    tile = suggestion_tile_html(Suggestion("home", "Topic", "<b>Title</b>", "Say <hi>"))
    assert "<b>" not in tile and "&lt;hi&gt;" in tile
