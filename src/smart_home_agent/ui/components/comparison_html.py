from smart_home_agent.models import NOT_LISTED, ComparisonResult
from smart_home_agent.ui.components._templates import Templates


class ComparisonHtml:
    """The <compare> table."""

    @staticmethod
    def render(result: ComparisonResult) -> str:
        """Rows where every product is "not listed" are left out; other "not listed" values stay verbatim."""
        rows = [
            row
            for row in result.rows
            if any(v != NOT_LISTED for v in row.values) and row.attribute != "data completeness"
        ]
        return Templates.render("comparison", "render", products=result.products, rows=rows, notes=result.notes)
