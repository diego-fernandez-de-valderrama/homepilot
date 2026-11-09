import streamlit as st

from smart_home_agent.agent import AgentReply


class DebugPanel:
    """Developer expander under an answer: language, guardrail, tools, candidates, compatibility and state."""

    @staticmethod
    def render(reply: AgentReply) -> None:
        trace = reply.trace
        with st.expander("Developer panel", icon=":material/bug_report:"):
            language = reply.state.language or reply.detected_language or "not detected"
            st.markdown(f"**Language:** `{language}` · **Intent:** `{trace.intent}`")
            DebugPanel._guardrail(reply)
            tools = ", ".join(f"`{c.name}` ({c.status})" for c in trace.tool_calls) or "none"
            st.markdown(f"**Tools called:** {tools}")
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

    @staticmethod
    def _guardrail(reply: AgentReply) -> None:
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
