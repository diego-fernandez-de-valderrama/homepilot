"""The script `streamlit run` executes: `uv run streamlit run src/smart_home_agent/ui/streamlit_app.py`.

See the `ui` package docstring for the flow."""

from smart_home_agent.ui import HomePilotApp

if __name__ == "__main__":  # `streamlit run` executes the script as __main__; importing it has no side effects
    HomePilotApp().run()
