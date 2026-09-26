"""Streamlit chat UI. Presentation only: every turn goes through `AgentService.chat`.

Run from the smart-home-agent directory (so `.env` is found):
    uv run streamlit run src/smart_home_agent/ui/streamlit_app.py
"""

import queue
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from functools import partial

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from smart_home_agent.agent.orchestrator import AgentService, build_agent
from smart_home_agent.agent.state import SessionState
from smart_home_agent.agent.trace import AgentReply
from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container
from smart_home_agent.models import rich
from smart_home_agent.models.cart import MAX_QUANTITY, CartConfirmation, CartView
from smart_home_agent.models.rich import RichContent
from smart_home_agent.ui.components import (
    ADVISOR_AVATAR,
    TYPING_HTML,
    ConfirmationState,
    Suggestion,
    answer_markdown,
    assistant_eyebrow_html,
    card_image_urls,
    cart_confirmation_html,
    cart_header_html,
    cart_line_html,
    cart_total_html,
    comparison_html,
    compatibility_html,
    confirm_button_label,
    confirmation_lead_html,
    decision_html,
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
    return AgentService(agent, settings.agent.app_name, container.services.rich_content, container.services.cart)


# Submits a turn to the agent service; called with the `on_tool_call` listener as keyword argument.
TurnStarter = Callable[..., Future[AgentReply]]


def run_turn(start: TurnStarter, progress: DeltaGenerator) -> AgentReply:
    """Runs one turn (`start` submits it) and shows real progress in `progress`:
    a neutral typing cue, then a status line only for the tools the model actually calls (a plain "hi"
    never shows a catalog status). The caller then writes the answer into the same slot, so the live
    message has the same layout as the history one."""
    calls: queue.SimpleQueue[str] = queue.SimpleQueue()
    future = start(on_tool_call=calls.put)
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
        st.session_state.decisions = {}  # confirmation request id -> the customer's choice
        st.session_state.submitted = set()  # request ids already answered in a confirmation turn
        st.session_state.expired = set()  # request ids left open when the customer typed a new message


# ---------- Cart ----------


def current_cart() -> CartView:
    """Read live from the agent session (the customer can change it without a turn). Before the first
    message the service is not built yet and the new session's cart is empty anyway."""
    if not st.session_state.messages:
        return CartView()
    return get_agent_service().cart(st.session_state.session_id)


def change_quantity(product_id: str, quantity: int) -> None:
    try:
        get_agent_service().set_cart_quantity(st.session_state.session_id, product_id, quantity)
    except ValueError:  # the line changed in the meantime (for example removed by the advisor)
        st.toast("That product is no longer in your cart.", icon=":material/info:")


def render_cart(view: CartView, busy: bool) -> None:
    """Sidebar cart: the customer can change quantities or remove lines; only the advisor adds products.
    `busy`: a turn runs in this script run, so edits wait until it is done."""
    st.html(cart_header_html(view))
    missing = missing_images(card_image_urls([line.product for line in view.lines if line.product]))
    for line in view.lines:
        pid = line.product_id
        with st.container(key=f"hp-cart-line-{pid}"):
            st.html(cart_line_html(line, missing))
            with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"hp-cart-step-{pid}"):
                st.button(
                    "",
                    icon=":material/remove:",
                    key=f"hp-cart-less-{pid}",
                    help="One less",
                    type="tertiary",
                    disabled=busy,
                    on_click=change_quantity,
                    args=(pid, line.quantity - 1),
                )
                st.html(f'<span class="hp-cart__qty" aria-label="Quantity">{line.quantity}</span>')
                st.button(
                    "",
                    icon=":material/add:",
                    key=f"hp-cart-more-{pid}",
                    help="One more",
                    type="tertiary",
                    disabled=busy or not line.available or line.quantity >= MAX_QUANTITY,
                    on_click=change_quantity,
                    args=(pid, line.quantity + 1),
                )
                st.button(
                    "",
                    icon=":material/delete:",
                    key=f"hp-cart-remove-{pid}",
                    help="Remove from cart",
                    type="tertiary",
                    disabled=busy,
                    on_click=change_quantity,
                    args=(pid, 0),
                )
    if view.lines:
        st.html(cart_total_html(view))


# ---------- Cart confirmations ----------


def open_confirmations() -> list[CartConfirmation]:
    """Changes of the latest answer that were neither answered nor expired (only the latest can be open)."""
    last = st.session_state.messages[-1] if st.session_state.messages else None
    reply = last.get("reply") if last and last["role"] == "assistant" else None
    if reply is None:
        return []
    done = st.session_state.submitted | st.session_state.expired
    return [c for c in reply.pending_confirmations if c.request_id not in done]


def ready_decisions() -> dict[str, bool] | None:
    """The customer's choices once every open change of the latest answer has one."""
    pending = open_confirmations()
    if not pending or any(c.request_id not in st.session_state.decisions for c in pending):
        return None
    return {c.request_id: st.session_state.decisions[c.request_id] for c in pending}


def decide(request_id: str, confirmed: bool) -> None:
    st.session_state.decisions[request_id] = confirmed


def confirmation_state(request_id: str) -> ConfirmationState:
    if request_id in st.session_state.expired:
        return "expired"
    if request_id in st.session_state.decisions:
        return "confirmed" if st.session_state.decisions[request_id] else "cancelled"
    return None


def render_confirmations(confirmations: list[CartConfirmation], interactive: bool) -> None:
    """One card per proposed change. Nothing changes before the customer clicks: the tool only runs
    after the confirmation turn.

    Every state renders the same element slots (lead line, then per card: card + actions). When the
    customer decides, the lead and the buttons turn into empty slots instead of disappearing: otherwise the
    elements below would shift up during the confirmation turn and Streamlit would keep the previous run's
    card in the freed slot as a faded duplicate until the answer is done."""
    products = [line.product for c in confirmations for line in c.lines if line.product]
    missing = missing_images(card_image_urls(products))
    lead = st.empty()
    if interactive and any(confirmation_state(c.request_id) is None for c in confirmations):
        lead.html(confirmation_lead_html(len(confirmations)))
    for confirmation in confirmations:
        rid = confirmation.request_id
        state = confirmation_state(rid)
        with st.container(key=f"hp-confirm-{rid}"):
            st.html(cart_confirmation_html(confirmation, state, missing))
            actions = st.empty()
            if state is None and interactive:
                with actions.container(horizontal=True, gap="small", key=f"hp-confirm-actions-{rid}"):
                    adding = confirmation.action == "add"
                    st.button(
                        confirm_button_label(confirmation),
                        icon=":material/add_shopping_cart:" if adding else ":material/remove_shopping_cart:",
                        key=f"hp-confirm-yes-{rid}",
                        type="primary",
                        on_click=decide,
                        args=(rid, True),
                    )
                    st.button("Cancel", key=f"hp-confirm-no-{rid}", on_click=decide, args=(rid, False))


def latest_state(messages: list[dict]) -> SessionState | None:
    replies = [m["reply"] for m in messages if m.get("reply") is not None]
    return replies[-1].state if replies else None


def render_sidebar(cart: CartView, busy: bool) -> bool:
    """Returns the developer toggle."""
    with st.sidebar:
        st.html('<p class="hp-rail-brand"><span class="hp-rail-brand__mark"></span>HomePilot</p>')
        st.html(setup_panel_html(latest_state(st.session_state.messages)))
        render_cart(cart, busy)
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


def render_message(message: dict, debug: bool, is_last: bool = False) -> None:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
        return
    if message["role"] == "decision":
        with st.chat_message("user"):
            st.html(decision_html(message["confirmed"], message["cancelled"]))
        return
    with st.chat_message("assistant", avatar=ADVISOR_AVATAR):
        st.html(assistant_eyebrow_html())
        reply = message.get("reply")
        if message["content"]:
            render_answer(message["content"], reply.rich if reply is not None else None)
        if reply is not None and reply.pending_confirmations:
            render_confirmations(reply.pending_confirmations, interactive=is_last)
        if debug and reply is not None:
            render_debug(reply)


def answer_turn(start: TurnStarter, debug: bool) -> bool:
    """Runs a turn in a new assistant message and stores it. Returns False when the backend failed."""
    with st.chat_message("assistant", avatar=ADVISOR_AVATAR):
        st.html(assistant_eyebrow_html())
        answer = st.empty()  # progress first, then the answer, at the same position as in render_message
        try:
            reply = run_turn(start, answer)
        except Exception as exc:  # the UI must survive backend failures (quota, network, database down)
            answer.error(f"Sorry, something went wrong: {type(exc).__name__}: {exc}")
            return False
        text = reply.text or ("" if reply.pending_confirmations else "_(no answer)_")
        with answer.container():
            message = {"role": "assistant", "content": text, "reply": reply}
            if text:
                render_answer(text, reply.rich)
            if reply.pending_confirmations:
                render_confirmations(reply.pending_confirmations, interactive=True)
            if debug:
                render_debug(reply)
    st.session_state.messages.append(message)
    return True


def main() -> None:
    st.set_page_config(page_title="HomePilot", page_icon=ADVISOR_AVATAR, layout="centered")
    inject_styles()
    inject_behaviour()
    init_session()

    prompt = st.chat_input("Ask about smart home products...", submit_mode="disable")
    if prompt:  # typing instead of deciding leaves the open changes unconfirmed (never sent later)
        st.session_state.expired |= {c.request_id for c in open_confirmations()}
    decisions = None if prompt else ready_decisions()

    cart = current_cart()
    debug = render_sidebar(cart, busy=bool(prompt or decisions))
    st.html(masthead_html(cart.item_count))

    messages = st.session_state.messages
    for index, message in enumerate(messages):
        render_message(message, debug, is_last=index == len(messages) - 1)

    session_id = st.session_state.session_id
    if decisions:
        st.session_state.submitted |= set(decisions)
        confirmed = sum(decisions.values())
        decision = {"role": "decision", "confirmed": confirmed, "cancelled": len(decisions) - confirmed}
        messages.append(decision)
        render_message(decision, debug)
        if not answer_turn(partial(get_agent_service().submit_confirmation, session_id, decisions), debug):
            messages.pop()  # the cards open again, so the customer can retry
            st.session_state.submitted -= set(decisions)
            for request_id in decisions:
                st.session_state.decisions.pop(request_id, None)
            return
        st.rerun()

    if not messages and not prompt:
        welcome = st.empty()
        with welcome.container():
            st.html(intro_html())
            prompt = suggestion_tiles(SUGGESTIONS)
        if prompt:
            welcome.empty()
    if not prompt:
        return

    user_message = {"role": "user", "content": prompt}
    messages.append(user_message)
    render_message(user_message, debug)
    if not answer_turn(partial(get_agent_service().submit, session_id, prompt), debug):
        messages.pop()
        return
    # Redraw from history (no agent call): the next turn then starts from exactly the layout it re-renders,
    # so no element of this run is left behind as a faded duplicate while the next answer is computed.
    st.rerun()


main()
