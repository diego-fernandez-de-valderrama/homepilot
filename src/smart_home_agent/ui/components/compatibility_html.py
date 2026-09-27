import html

from smart_home_agent.models import Product, ProductCompatibility
from smart_home_agent.ui.components._markup import Markup
from smart_home_agent.ui.components._texts import OVERALL_TEXT, REQUIREMENT_TEXT, STATUS_TEXT


class CompatibilityHtml:
    """The <compatibility> block: one chip per check, requirements as notes."""

    @staticmethod
    def render(product: Product, compatibility: ProductCompatibility) -> str:
        result = compatibility.result
        heading = (
            f'<p class="hp-compat__overall hp-compat__overall--{result.overall.value}">'
            f"{html.escape(OVERALL_TEXT[result.overall])}</p>"
            if compatibility.against_setup and result.checks
            else '<p class="hp-compat__overall">Compatibility listed in the catalog</p>'
        )
        chips = (
            "".join(
                f'<span class="hp-compat-chip hp-compat-chip--{c.status.value}">{html.escape(c.label)}'
                f'<span class="hp-compat-chip__status">{html.escape(STATUS_TEXT[c.status])}</span></span>'
                for c in result.checks
            )
            or '<span class="hp-compat__empty">The catalog lists no compatibility information.</span>'
        )
        requirements = [
            f"Requires {r.label}" + (f" ({REQUIREMENT_TEXT[r.status]})" if r.status in REQUIREMENT_TEXT else "")
            for r in result.requirements
            if r.status != "info"
        ]
        if result.requires_professional_installation:
            requirements.append("Installation by a qualified electrician required")
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in requirements)
        return (
            '<section class="hp-compat">'
            f'<p class="hp-compat__title">{html.escape(product.title)}</p>{Markup.version(product, "hp-compat")}'
            f"{heading}"
            f'<div class="hp-compat__chips">{chips}</div>'
            + (f'<ul class="hp-compat__notes">{notes}</ul>' if notes else "")
            + "</section>"
        )
