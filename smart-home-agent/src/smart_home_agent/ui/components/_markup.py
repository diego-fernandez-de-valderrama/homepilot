import html
import re

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#+!|$~])")


class Markup:
    """Formatting and escaping helpers shared by the components (template filters: `price`, `safe_url`,
    `markdown_literal`)."""

    @staticmethod
    def price(value: float | None) -> str:
        return f"{value:,.2f} €" if value is not None else "price not listed"

    @staticmethod
    def safe_url(url: str | None) -> str | None:
        return url if url and url.startswith(("https://", "http://")) else None

    @staticmethod
    def markdown_literal(value: str) -> str:
        """Text placed between HTML tags inside markdown is still parsed as markdown: neutralize its syntax."""
        # quote=False: only text nodes use this, and "&#x27;" would get its "#" escaped and show up literally.
        return _MARKDOWN_SPECIAL.sub(r"\\\1", html.escape(value, quote=False))
