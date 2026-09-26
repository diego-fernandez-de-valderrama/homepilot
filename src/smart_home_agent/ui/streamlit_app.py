"""Streamlit chat UI. Presentation only: every turn goes through `AgentService.chat`.

Run from the smart-home-agent directory (so `.env` is found):
    uv run streamlit run src/smart_home_agent/ui/streamlit_app.py
"""

import uuid

import streamlit as st

from smart_home_agent.agent.orchestrator import AgentService, build_agent
from smart_home_agent.agent.trace import AgentReply
from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container

SUGGESTIONS = {
    ":material/thermostat: Thermostat for Google Home": "I need a thermostat compatible with Google Home.",
    ":material/sensors: HomeKit motion sensor": "I have HomeKit and I'm looking for a motion sensor.",
    ":material/euro: Alexa, max 150 €": "Ich suche etwas für Alexa, das nicht mehr als 150 € kostet.",
}


@st.cache_resource(show_spinner="Connecting to the catalog...")
def get_agent_service() -> AgentService:
    settings = get_settings()
    container = build_container(settings)
    return AgentService(build_agent(container.services, settings), settings.agent.app_name)


def init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []


def render_debug(reply: AgentReply) -> None:
    trace = reply.trace
    with st.expander("Developer panel", icon=":material/bug_report:"):
        language = reply.state.language or reply.detected_language or "not detected"
        st.markdown(f"**Language:** `{language}` · **Intent:** `{trace.intent}`")
        st.markdown("**Tools called:** " + (", ".join(f"`{c.name}` ({c.status})" for c in trace.tool_calls) or "none"))
        if trace.search_queries:
            st.markdown("**Search queries**")
            st.json(trace.search_queries, expanded=False)
        if reply.state.candidate_products:
            st.markdown(f"**Candidates:** {', '.join(reply.state.candidate_products)}")
        if trace.compatibility:
            st.markdown("**Compatibility results**")
            st.dataframe(trace.compatibility, hide_index=True)
        st.markdown(f"**Selected products:** {', '.join(reply.state.selected_products) or 'none'}")
        st.markdown("**Session state**")
        st.json(reply.state.model_dump(mode="json"), expanded=False)
        st.markdown("**Raw tool calls**")
        st.json([c.model_dump(mode="json") for c in trace.tool_calls], expanded=False)


def render_message(message: dict, debug: bool) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if debug and message.get("reply") is not None:
            render_debug(message["reply"])


def main() -> None:
    st.set_page_config(page_title="HomePilot", page_icon=":material/home:")
    init_session()

    with st.sidebar:
        st.header("HomePilot")
        st.caption("Smart home advisor · English / Deutsch")
        debug = st.toggle("Developer panel", value=False, help="Show language, tools, candidates and compatibility.")
        if st.button("New conversation", icon=":material/refresh:"):
            st.session_state.clear()
            st.rerun()

    st.title("HomePilot smart home advisor")

    for message in st.session_state.messages:
        render_message(message, debug)

    prompt = st.chat_input("Ask about smart home products...", submit_mode="disable")
    if not st.session_state.messages and not prompt:
        selected = st.pills("Try asking:", list(SUGGESTIONS), label_visibility="collapsed")
        if selected:
            prompt = SUGGESTIONS[selected]
    if not prompt:
        return

    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    render_message(user_message, debug)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Checking the catalog..."):
                reply = get_agent_service().chat(st.session_state.session_id, prompt)
        except Exception as exc:  # the UI must survive backend failures (quota, network, database down)
            st.error(f"Sorry, something went wrong: {type(exc).__name__}: {exc}")
            st.session_state.messages.pop()
            return
        text = reply.text or "_(no answer)_"
        st.markdown(text)
        if debug:
            render_debug(reply)
    st.session_state.messages.append({"role": "assistant", "content": text, "reply": reply})


main()
