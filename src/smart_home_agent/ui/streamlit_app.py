"""Streamlit chat UI. Presentation only: every turn goes through `AgentService.chat`.

Run from the smart-home-agent directory (so `.env` is found):
    uv run streamlit run src/smart_home_agent/ui/streamlit_app.py
"""

import logging
import queue
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from functools import partial
from typing import Any

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from smart_home_agent.agent.language import detect_language
from smart_home_agent.agent.orchestrator import DEFAULT_USER, AgentService, build_agent
from smart_home_agent.agent.state import SessionState
from smart_home_agent.agent.trace import AgentReply
from smart_home_agent.config import get_settings
from smart_home_agent.container import build_container, build_profile_store
from smart_home_agent.models import rich
from smart_home_agent.models.cart import MAX_QUANTITY, CartConfirmation, CartView
from smart_home_agent.models.profile import CustomerSummary
from smart_home_agent.models.rich import RichContent
from smart_home_agent.services.profile import ProfileService
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
    failure_html,
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

logger = logging.getLogger(__name__)

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
    services = container.services
    return AgentService(agent, settings.agent.app_name, services.rich_content, services.cart, services.profile)


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


# Session keys that survive "New conversation" and a customer switch (the customer and the picker widgets).
_CUSTOMER_KEYS = frozenset(
    {"customer_id", "known_customers", "hp-customer-pick", "hp-customer-new", "hp-customer-options"}
)
NEW_CUSTOMER = "__new_customer__"  # picker option that asks for a new customer id


def init_session() -> None:
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = DEFAULT_USER
    if "known_customers" not in st.session_state:
        st.session_state.known_customers = []  # created in this browser session, maybe nothing stored yet
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.decisions = {}  # confirmation request id -> the customer's choice
        st.session_state.submitted = set()  # request ids already answered in a confirmation turn
        st.session_state.expired = set()  # request ids left open when the customer typed a new message
        st.session_state.cart_open = False  # the customer panel (cart and setup) on the right


# ---------- Cart ----------


def current_cart() -> CartView:
    """Read live from the agent session (the customer can change it without a turn). Before the first
    message the service is not built yet and the new session's cart is empty anyway."""
    if not st.session_state.messages:
        return CartView()
    return get_agent_service().cart(st.session_state.session_id, st.session_state.customer_id)


def change_quantity(product_id: str, quantity: int) -> None:
    try:
        get_agent_service().set_cart_quantity(
            st.session_state.session_id, product_id, quantity, st.session_state.customer_id
        )
    except ValueError:  # the line changed in the meantime (for example removed by the advisor)
        st.toast("That product is no longer in your cart.", icon=":material/info:")


def render_cart(view: CartView, busy: bool) -> None:
    """Cart lines in the customer panel: the customer can change quantities or remove lines; only the advisor
    adds products. `busy`: a turn runs in this script run, so edits wait until it is done."""
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


def toggle_cart() -> None:
    st.session_state.cart_open = not st.session_state.cart_open


def render_masthead(cart: CartView, busy: bool) -> None:
    """Pinned masthead: the brand, "New conversation" and the cart button that opens the customer panel."""
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key="hp-masthead"):
        st.html(masthead_html())
        if st.button("New conversation", icon=":material/refresh:", key="hp-new-conversation", disabled=busy):
            reset_conversation()
            st.rerun()
        count = cart.item_count
        label = f"{count} item{'s' if count != 1 else ''} in your cart"
        st.button(
            str(count),
            icon=":material/shopping_cart:",
            key=f"hp-cart-toggle-{'filled' if count else 'empty'}",  # the key suffix drives the filled style
            help=f"{label}. Click to {'hide' if st.session_state.cart_open else 'show'} your cart.",
            on_click=toggle_cart,
            disabled=busy,  # a click would rerun the script and cut off the running turn
        )


def render_cart_panel(cart: CartView, busy: bool) -> None:
    """The customer panel on the right (pinned by CSS): the cart, then what the advisor knows about the setup.
    The dark sidebar on the left holds only developer and testing controls."""
    if not st.session_state.cart_open:
        return
    with st.container(key="hp-cart-panel"):
        with st.container(horizontal=True, vertical_alignment="center", key="hp-cart-panel-head"):
            st.html(cart_header_html(cart))
            st.button(
                "",
                icon=":material/close:",
                key="hp-cart-close",
                help="Hide your cart",
                on_click=toggle_cart,
                disabled=busy,
            )
        render_cart(cart, busy)
        st.html(setup_panel_html(latest_state(st.session_state.messages)))


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


def reset_conversation() -> None:
    """Starts a new conversation for the same customer: their stored memory carries over."""
    for key in list(st.session_state.keys()):
        if key not in _CUSTOMER_KEYS:
            del st.session_state[key]
    init_session()


def switch_customer(customer: str) -> None:
    """Another customer: a new conversation, with that customer's memory. Both stay in the picker for this
    browser session, even while nothing is stored for them yet."""
    if customer != st.session_state.customer_id:
        known = [st.session_state.customer_id, *st.session_state.known_customers, customer]
        st.session_state.known_customers = list(dict.fromkeys(known))
        st.session_state.customer_id = customer
        reset_conversation()


def pick_customer() -> None:
    choice = st.session_state["hp-customer-pick"]
    if choice not in st.session_state.get("hp-customer-options", []):
        # Not an option of the picker as drawn: the browser sent a stale value (it keeps a selectbox's value as
        # the displayed text). Never treat it as a customer id: keep the current customer.
        st.session_state["hp-customer-pick"] = st.session_state.customer_id
        return
    if choice != NEW_CUSTOMER:  # "New customer..." only reveals the id field
        switch_customer(choice)


def create_customer() -> None:
    """The id typed for a new customer (Enter): it is selected at once, before anything is stored for it."""
    customer = st.session_state["hp-customer-new"].strip()
    st.session_state["hp-customer-new"] = ""
    if not customer or customer in (NEW_CUSTOMER, customer_label(NEW_CUSTOMER)):  # labels must stay unique
        return
    st.session_state["hp-customer-pick"] = customer
    switch_customer(customer)


@st.cache_resource(show_spinner=False)
def get_customer_directory() -> ProfileService | None:
    """Reads the customer memory only (no Gemini or Qdrant), so the picker works before the first message."""
    store = build_profile_store(get_settings())
    return ProfileService(store) if store is not None else None


@st.cache_data(ttl=5, show_spinner=False)
def stored_customers() -> list[CustomerSummary] | None:
    """Customers with stored facts, most recently active first; None when the memory is off or unreachable.
    Cached for a few seconds, so reruns (every click) do not query the database each time."""
    directory = get_customer_directory()
    if directory is None:
        return None
    try:
        return directory.customers()
    except Exception:
        logger.warning("customer memory: listing the customers failed", exc_info=True)
        return None


def customer_options(stored: list[CustomerSummary] | None, current: str, known: list[str]) -> list[str]:
    """Stored customers first (most recent first), then this session's other customers in the order they were
    used, then "New customer...". The order stays stable while switching."""
    ids = [c.user_id for c in stored or []]
    ids += [c for c in dict.fromkeys([*known, current]) if c not in ids]
    return [*ids, NEW_CUSTOMER]


def customer_label(option: str) -> str:
    """The displayed text of a picker option. It must never change for the same customer: Streamlit's browser
    side keeps the selection as this text, so a changing label (e.g. with a fact count) is sent back as an
    unknown value on the next interaction."""
    return "+ New customer…" if option == NEW_CUSTOMER else option


def stored_facts_caption(customer: str, stored: list[CustomerSummary] | None) -> str:
    """What is stored for the selected customer (shown under the picker, never in the option labels)."""
    if stored is None:
        return "Stored customers are not available (customer memory off or not reachable)."
    summary = next((c for c in stored if c.user_id == customer), None)
    if summary is None or summary.active_facts == 0:
        return "Nothing stored for this customer yet."
    return f"{summary.active_facts} fact{'s' if summary.active_facts != 1 else ''} stored for this customer."


def render_customer_picker(stored: list[CustomerSummary] | None, busy: bool) -> None:
    """Testing aid: pick a stored customer instead of remembering ids. Switching starts a new conversation."""
    options = customer_options(stored, st.session_state.customer_id, st.session_state.known_customers)
    st.session_state["hp-customer-options"] = options  # for pick_customer: values outside it are stale
    if st.session_state.get("hp-customer-pick") not in options:
        st.session_state["hp-customer-pick"] = st.session_state.customer_id
    st.selectbox(
        "Customer",
        options,
        key="hp-customer-pick",
        format_func=customer_label,
        on_change=pick_customer,
        disabled=busy,
        help="Each customer has their own memory. Switching starts a new conversation with that customer.",
    )
    if st.session_state["hp-customer-pick"] == NEW_CUSTOMER:
        st.text_input(
            "New customer id",
            key="hp-customer-new",
            placeholder="e.g. anna, then press Enter",
            on_change=create_customer,
            disabled=busy,
        )
    else:
        st.caption(stored_facts_caption(st.session_state.customer_id, stored))


@st.dialog("Stored data about this customer", width="large")
def show_customer_memory(customer_id: str) -> None:
    """Developer view: everything the memory database holds about the customer, retracted facts included."""
    try:
        profile = get_agent_service().profile(customer_id, include_retracted=True)
    except Exception as exc:  # the memory database may be down or not initialized
        st.error(f"The customer memory could not be read: {type(exc).__name__}: {exc}")
        return
    if profile is None:
        st.info("The customer memory is disabled (AGENT_MEMORY_ENABLED=false).")
        return
    st.markdown(f"**Customer:** `{customer_id}` · {len(profile.active())} active, {len(profile.facts)} total facts")
    if not profile.facts:
        st.caption("Nothing stored yet.")
        return
    st.dataframe(
        [
            {
                "kind": f.kind.value,
                "value": f.value,
                "label": f.label,
                "canonical": f.canonical,
                "evidence": f.evidence,
                "active": f.active,
                "created": f.created_at,
                "retracted": f.retracted_at,
                "retracted because": f.retracted_evidence,
                "conversation": f.session_id,
            }
            for f in profile.facts
        ],
        hide_index=True,
    )
    st.json(profile.model_dump(mode="json"), expanded=False)


def render_sidebar(busy: bool) -> bool:
    """The dark rail: developer and testing controls only (customer content lives in the customer panel).
    Returns the developer toggle."""
    with st.sidebar:
        st.html('<p class="hp-rail-brand"><span class="hp-rail-brand__mark"></span>HomePilot</p>')
        st.html('<p class="hp-rail-label">Testing</p>')
        render_customer_picker(stored_customers(), busy)
        st.html('<p class="hp-rail-label">Developer</p>')
        debug = st.toggle("Developer panel", key="hp-debug", help="Show language, tools, candidates and compatibility.")
        if debug and st.button("Stored data about me", icon=":material/person_search:", width="stretch"):
            show_customer_memory(st.session_state.customer_id)
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
        if reply.profile is not None:
            st.markdown("**Customer profile (end of this turn)**")
            st.json([f"{f.kind.value}: {f.value}" for f in reply.profile.active()], expanded=False)
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
        if message.get("failed"):
            show_failure(message.get("language"), debug, reply.error if reply is not None else None)
        if message["content"]:
            render_answer(message["content"], reply.rich if reply is not None else None)
        if reply is not None and reply.pending_confirmations:
            render_confirmations(reply.pending_confirmations, interactive=is_last)
        if debug and reply is not None:
            render_debug(reply)


def reply_language(prompt: str | None) -> str | None:
    """Language for interface messages of this turn: the prompt's, else the conversation's."""
    detected = detect_language(prompt) if prompt else None
    state = latest_state(st.session_state.messages)
    return detected or (state.language if state else None)


def show_failure(language: str | None, debug: bool, detail: str | None) -> None:
    """A friendly notice instead of the answer; the technical detail only in developer mode (and the log)."""
    st.html(failure_html(language))
    if debug and detail:
        st.caption(f"Developer detail: {detail}")


def applied_confirmations(session_id: str, request_ids: list[str], customer_id: str) -> set[str]:
    try:
        return get_agent_service().applied_confirmations(session_id, request_ids, customer_id)
    except Exception:  # unknown: treat every change as applied rather than risk applying one twice
        logger.exception("reading the applied cart changes failed")
        return set(request_ids)


def answer_turn(start: TurnStarter, debug: bool, language: str | None) -> bool:
    """Runs a turn in a new assistant message and stores it. The model call is already retried silently
    (agent/model.py), so a failure is shown as a friendly notice:
    - the turn ran but produced nothing to show (empty answer after all retries): stored in the history as a
      failed message, since its tools (e.g. a confirmed cart change) did run; returns True;
    - the backend raised: nothing is stored and False is returned, so the caller can offer a retry."""
    with st.chat_message("assistant", avatar=ADVISOR_AVATAR):
        st.html(assistant_eyebrow_html())
        answer = st.empty()  # progress first, then the answer, at the same position as in render_message
        try:
            reply = run_turn(start, answer)
        except Exception as exc:  # the UI must survive backend failures (quota, network, database down)
            logger.exception("turn failed")
            with answer.container():
                show_failure(language, debug, f"{type(exc).__name__}: {exc}")
            return False
        text = reply.text
        with answer.container():
            message: dict[str, Any] = {"role": "assistant", "content": text, "reply": reply}
            if reply.failed:
                message |= {"failed": True, "language": reply.detected_language or language}
                show_failure(message["language"], debug, reply.error or "empty answer")
            if text:
                render_answer(text, reply.rich)
            if reply.pending_confirmations:
                render_confirmations(reply.pending_confirmations, interactive=True)
            if debug:
                render_debug(reply)
    st.session_state.messages.append(message)
    stored_customers.clear()  # the turn may have stored facts: the picker shows fresh counts
    return True


def main() -> None:
    st.set_page_config(page_title="HomePilot", page_icon=ADVISOR_AVATAR, layout="centered")
    inject_styles()
    inject_behaviour()
    init_session()

    # An open cart change blocks the input: the customer answers it on its card first.
    awaiting_decision = bool(open_confirmations())
    placeholder = (
        "Confirm or cancel the cart change above to continue"
        if awaiting_decision
        else "Ask about smart home products..."
    )
    prompt = st.chat_input(placeholder, submit_mode="disable", disabled=awaiting_decision)
    if prompt:  # guard only (the input is disabled then): the open changes stay unconfirmed, never sent later
        st.session_state.expired |= {c.request_id for c in open_confirmations()}
    decisions = None if prompt else ready_decisions()

    busy = bool(prompt or decisions)
    debug = render_sidebar(busy)
    cart = current_cart()
    render_masthead(cart, busy)
    render_cart_panel(cart, busy)

    messages = st.session_state.messages
    for index, message in enumerate(messages):
        render_message(message, debug, is_last=index == len(messages) - 1)

    session_id = st.session_state.session_id
    customer_id = st.session_state.customer_id
    if decisions:
        adds = {c.request_id for c in open_confirmations() if c.action == "add"}
        st.session_state.submitted |= set(decisions)
        confirmed = sum(decisions.values())
        decision = {"role": "decision", "confirmed": confirmed, "cancelled": len(decisions) - confirmed}
        messages.append(decision)
        render_message(decision, debug)
        confirm = partial(get_agent_service().submit_confirmation, session_id, decisions, customer_id)
        if not answer_turn(confirm, debug, reply_language(None)):
            # The turn may have failed after a cart change was applied: only the others open again for a retry.
            retry = set(decisions) - applied_confirmations(session_id, list(decisions), customer_id)
            if len(retry) == len(decisions):
                messages.pop()  # nothing happened: the cards open again, so the customer can retry
            st.session_state.submitted -= retry
            for request_id in retry:
                st.session_state.decisions.pop(request_id, None)
            return
        if any(decisions[r] for r in adds):  # show the customer what they just added
            st.session_state.cart_open = True
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
    if not answer_turn(
        partial(get_agent_service().submit, session_id, prompt, customer_id), debug, reply_language(prompt)
    ):
        messages.pop()
        return
    # Redraw from history (no agent call): the next turn then starts from exactly the layout it re-renders,
    # so no element of this run is left behind as a faded duplicate while the next answer is computed.
    st.rerun()


main()
