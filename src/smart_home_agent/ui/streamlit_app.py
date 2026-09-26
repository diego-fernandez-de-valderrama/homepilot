"""Streamlit chat UI. Presentation only: every turn goes through `AgentService.chat`.

Run from the smart-home-agent directory (so `.env` is found):
    uv run streamlit run src/smart_home_agent/ui/streamlit_app.py
"""

import queue
import time
import uuid

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from smart_home_agent.agent.orchestrator import AgentService, build_agent
from smart_home_agent.agent.state import SessionState
from smart_home_agent.agent.trace import AgentReply
from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models import rich
from smart_home_agent.models.rich import RichContent
from smart_home_agent.ui.components import (
    ADVISOR_AVATAR,
    TYPING_HTML,
    Suggestion,
    answer_markdown,
    assistant_eyebrow_html,
    card_image_urls,
    comparison_html,
    compatibility_html,
    inject_behaviour,
    inject_styles,
    intro_html,
    masthead_html,
    product_cards_html,
    setup_panel_html,
    suggestion_tiles,
    tool_progress_html,
    tool_status_label,
    upgrade_html,
)
from smart_home_agent.ui.images import missing_images

SUGGESTIONS = [
    Suggestion(
        "thermostat", "Heating", "Thermostat for Google Home", "I need a thermostat compatible with Google Home."
    ),
    Suggestion("sensors", "Security", "HomeKit motion sensor", "I have HomeKit and I'm looking for a motion sensor."),
    Suggestion("euro", "Budget", "Alexa, max 150 €", "Ich suche etwas für Alexa, das nicht mehr als 150 € kostet."),
]


@st.cache_resource(show_spinner="Starting HomePilot...")
def get_agent_service() -> AgentService:
    settings = get_settings()
    container = build_container(settings)
    agent = build_agent(container.services, settings, container.guardrail)
    return AgentService(agent, settings.agent.app_name, container.services.rich_content)


def run_turn(prompt: str, progress: DeltaGenerator) -> AgentReply:
    """Runs one turn and shows real progress in `progress`: a neutral typing cue, then a status line only
    for the tools the model actually calls (a plain "hi" never shows a catalog status). The caller then
    writes the answer into the same slot, so the live message has the same layout as the history one."""
    calls: queue.SimpleQueue[str] = queue.SimpleQueue()
    future = get_agent_service().submit(st.session_state.session_id, prompt, on_tool_call=calls.put)
    progress.html(TYPING_HTML)
    shown = None
    while not future.done():
        label = shown
        while not calls.empty():
            label = tool_status_label(calls.get())
        if label is not None and label != shown:
            progress.html(tool_progress_html(label))
            shown = label
        time.sleep(0.15)
    return future.result()


def init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []


def latest_state(messages: list[dict]) -> SessionState | None:
    replies = [m["reply"] for m in messages if m.get("reply") is not None]
    return replies[-1].state if replies else None


def render_sidebar() -> bool:
    """Returns the developer toggle."""
    with st.sidebar:
        st.html('<p class="hp-rail-brand"><span class="hp-rail-brand__mark"></span>HomePilot</p>')
        st.html(setup_panel_html(latest_state(st.session_state.messages)))
        st.html('<p class="hp-rail-label">Conversation</p>')
        if st.button("New conversation", icon=":material/refresh:", type="primary", width="stretch"):
            st.session_state.clear()
            st.rerun()
        st.html('<p class="hp-rail-label">Developer</p>')
        debug = st.toggle("Developer panel", value=False, help="Show language, tools, candidates and compatibility.")
        st.html('<p class="hp-rail-footer">Answers based on the HomePilot catalog · EN / DE</p>')
    return debug


def render_debug(reply: AgentReply) -> None:
    trace = reply.trace
    with st.expander("Developer panel", icon=":material/bug_report:"):
        language = reply.state.language or reply.detected_language or "not detected"
        st.markdown(f"**Language:** `{language}` · **Intent:** `{trace.intent}`")
        guardrail = reply.guardrail
        if guardrail and guardrail.input:
            decision = guardrail.input
            st.markdown(
                f"**Guardrail:** `{decision.category}` (top `{decision.top_category}` "
                f"{decision.score:.3f}, margin {decision.margin:.3f})"
                + (f" · reply `{guardrail.response_type}`" if guardrail.response_type else "")
            )
        if guardrail and guardrail.output_violations:
            st.markdown("**Output check:** " + ", ".join(f"`{v.kind}`" for v in guardrail.output_violations))
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


def render_answer(text: str, content: RichContent | None) -> None:
    """Markdown with the answer tags replaced by catalog components. A tag without resolved data is dropped
    (blocks) or shown as its id (inline); the raw tag is never shown."""
    if content is None:
        st.markdown(rich.to_plain(text, {}))
        return
    segments = rich.parse(text)
    in_blocks = rich.block_ids(segments)
    missing = missing_images(card_image_urls(list(content.products.values())))  # one cached check per answer
    for segment in segments:
        match segment:
            case rich.TextSegment(body):
                st.markdown(answer_markdown(body, content.products, in_blocks, missing), unsafe_allow_html=True)
            case rich.ItemsBlock(ids):
                products = [content.products[pid] for pid in ids if pid in content.products]
                if products:
                    st.html(product_cards_html(products, missing))
            case rich.CompareBlock(ids):
                if (comparison := content.comparisons.get(rich.compare_key(ids))) is not None:
                    st.html(comparison_html(comparison))
            case rich.CompatibilityBlock(product_id):
                if (compatibility := content.compatibility.get(product_id)) is not None:
                    st.html(compatibility_html(content.products[product_id], compatibility))
            case rich.UpgradeBlock(from_id, to_id):
                if (upsell := content.upgrades.get(rich.upgrade_key(from_id, to_id))) is not None:
                    st.html(upgrade_html(content.products[from_id], content.products[to_id], upsell))


def render_message(message: dict, debug: bool) -> None:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
        return
    with st.chat_message("assistant", avatar=ADVISOR_AVATAR):
        st.html(assistant_eyebrow_html())
        reply = message.get("reply")
        render_answer(message["content"], reply.rich if reply is not None else None)
        if debug and message.get("reply") is not None:
            render_debug(message["reply"])


def main() -> None:
    st.set_page_config(page_title="HomePilot", page_icon=ADVISOR_AVATAR, layout="centered")
    inject_styles()
    inject_behaviour()
    init_session()
    debug = render_sidebar()
    st.html(masthead_html())

    for message in st.session_state.messages:
        render_message(message, debug)

    prompt = st.chat_input("Ask about smart home products...", submit_mode="disable")
    if not st.session_state.messages and not prompt:
        welcome = st.empty()
        with welcome.container():
            st.html(intro_html())
            prompt = suggestion_tiles(SUGGESTIONS)
        if prompt:
            welcome.empty()
    if not prompt:
        return

    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    render_message(user_message, debug)

    with st.chat_message("assistant", avatar=ADVISOR_AVATAR):
        st.html(assistant_eyebrow_html())
        answer = st.empty()  # progress first, then the answer, at the same position as in render_message
        try:
            reply = run_turn(prompt, answer)
        except Exception as exc:  # the UI must survive backend failures (quota, network, database down)
            answer.error(f"Sorry, something went wrong: {type(exc).__name__}: {exc}")
            st.session_state.messages.pop()
            return
        text = reply.text or "_(no answer)_"
        with answer.container():
            render_answer(text, reply.rich)
    st.session_state.messages.append({"role": "assistant", "content": text, "reply": reply})
    # Redraw from history (no agent call): the next turn then starts from exactly the layout it re-renders,
    # so no element of this run is left behind as a faded duplicate while the next answer is computed.
    st.rerun()


main()
