import html

from catalog_ingestion.vocabulary import FactStatus

from smart_home_agent.models import NOT_LISTED, ComparisonResult
from smart_home_agent.ui.components._markup import Markup
from smart_home_agent.ui.components._texts import STATUS_TEXT


class ComparisonHtml:
    """The <compare> table."""

    @staticmethod
    def render(result: ComparisonResult) -> str:
        """Rows where every product is "not listed" are left out; other "not listed" values stay verbatim."""
        head = "".join(
            f'<th scope="col">{html.escape(p.title)}{Markup.version(p, "hp-compare")}'
            f'<span class="hp-compare__price">{html.escape(Markup.price(p.price))}</span></th>'
            for p in result.products
        )
        rows = "".join(
            ('<tr class="hp-compare__differs">' if row.differs else "<tr>")
            + f'<th scope="row">{html.escape(row.attribute)}</th>'
            + "".join(ComparisonHtml._cell(row.group, v) for v in row.values)
            + "</tr>"
            for row in result.rows
            if any(v != NOT_LISTED for v in row.values) and row.attribute != "data completeness"
        )
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in result.notes)
        return (
            '<div class="hp-compare"><table>'
            f"<thead><tr><td></td>{head}</tr></thead><tbody>{rows}</tbody></table>"
            f'<ul class="hp-compare__notes">{notes}</ul></div>'
        )

    @staticmethod
    def _cell(group: str, value: str) -> str:
        status = value.split(" ", 1)[0]
        if group != "compatibility" or status not in FactStatus:
            return f"<td>{html.escape(value)}</td>"
        return f'<td class="hp-compare__status hp-compare__status--{status}">{STATUS_TEXT[FactStatus(status)]}</td>'
