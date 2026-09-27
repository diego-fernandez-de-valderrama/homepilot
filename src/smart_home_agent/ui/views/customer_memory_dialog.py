import streamlit as st

from smart_home_agent.ui.backend import CustomerDirectory


class CustomerMemoryDialog:
    """Developer view: everything the memory database holds about the customer, retracted facts included."""

    @staticmethod
    @st.dialog("Stored data about this customer", width="large")
    def show(customer_id: str) -> None:
        directory = CustomerDirectory.service()  # memory only: no agent (Gemini, Qdrant) needed for this view
        if directory is None:
            st.info("The customer memory is disabled (AGENT_MEMORY_ENABLED=false).")
            return
        try:
            profile = directory.profile(customer_id, include_retracted=True)
        except Exception as exc:  # the memory database may be down or not initialized
            st.error(f"The customer memory could not be read: {type(exc).__name__}: {exc}")
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
