"""Streamlit chat UI. Presentation only: every turn goes through `AgentService` (via `backend.AgentBackend`).

    uv run streamlit run src/smart_home_agent/ui/streamlit_app.py    # from the smart-home-agent directory

`streamlit_app.py` is only the script Streamlit runs; `HomePilotApp.run` is one script run:
1. page setup: `PageAssets` (stylesheet, hover-card script, avatar) and `state.UiSession.init`;
2. input: the typed message or a queued welcome tile, else the customer's decisions on the open cart changes
   once all are decided (`state.ConfirmationTracker`). Either makes the run `busy` (widgets that would rerun
   the script are disabled);
3. frame: `views.Sidebar` (testing and developer controls), `views.Masthead`, `views.CartPanel` (cart and
   setup, reading the live cart through `backend.AgentBackend`);
4. history: `views.MessageView` for every stored message;
5. the turn: `turns.ConfirmationTurn` or `turns.MessageTurn` (both via `turns.AnswerTurn`), then a rerun that
   redraws from the history; with nothing to answer and no history, `views.Welcome`.

Layers inside `ui/` only call downward: `app` -> `turns` -> `views` -> `state`, `backend` -> `components` (pure HTML
builders, no Streamlit).
"""

from smart_home_agent.ui.app import HomePilotApp

__all__ = ["HomePilotApp"]
