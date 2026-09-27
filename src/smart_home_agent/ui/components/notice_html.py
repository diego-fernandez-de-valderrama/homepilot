import html

from smart_home_agent.ui.components._texts import FAILURE_TEXT


class NoticeHtml:
    """Messages that stand in for a text: the failure notice and the customer's cart decision."""

    @staticmethod
    def failure(language: str | None) -> str:
        """Shown instead of an answer when the turn failed (after the silent retries): no technical details."""
        title, hint = FAILURE_TEXT.get(language or "en", FAILURE_TEXT["en"])
        return (
            '<div class="hp-failure" role="alert">'
            f'<p class="hp-failure__title">{html.escape(title)}</p>'
            f'<p class="hp-failure__hint">{html.escape(hint)}</p></div>'
        )

    @staticmethod
    def decision(confirmed: int, cancelled: int) -> str:
        """The customer's side of a confirmation turn in the history (no free text was typed)."""
        parts = []
        if confirmed:
            parts.append(f"Confirmed {confirmed} change{'s' if confirmed != 1 else ''}")
        if cancelled:
            parts.append(f"Cancelled {cancelled} change{'s' if cancelled != 1 else ''}")
        return f'<p class="hp-decision">{html.escape(" · ".join(parts))}</p>'
