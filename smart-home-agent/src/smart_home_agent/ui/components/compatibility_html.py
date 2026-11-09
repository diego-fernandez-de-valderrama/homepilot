from smart_home_agent.models import Product, ProductCompatibility
from smart_home_agent.ui.components._templates import Templates
from smart_home_agent.ui.components._texts import REQUIREMENT_TEXT


class CompatibilityHtml:
    """The <compatibility> block: one chip per check, requirements as notes."""

    @staticmethod
    def render(product: Product, compatibility: ProductCompatibility) -> str:
        result = compatibility.result
        notes = [
            f"Requires {r.label}" + (f" ({REQUIREMENT_TEXT[r.status]})" if r.status in REQUIREMENT_TEXT else "")
            for r in result.requirements
            if r.status != "info"
        ]
        if result.requires_professional_installation:
            notes.append("Installation by a qualified electrician required")
        return Templates.render("compatibility", "render", product=product, compatibility=compatibility, notes=notes)
