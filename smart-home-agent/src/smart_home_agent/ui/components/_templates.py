from functools import cache
from typing import Any

import markupsafe
from jinja2 import Environment, PackageLoader, StrictUndefined

from smart_home_agent.ui.components._compact_source import CompactSource
from smart_home_agent.ui.components._markup import Markup
from smart_home_agent.ui.components._texts import OVERALL_TEXT, STATUS_TEXT


class Templates:
    """The Jinja2 templates in `templates/`: one file per component, one macro per public method.

    Autoescape is on, so every value is escaped unless a macro or the `markdown_literal` filter produced it.
    """

    @staticmethod
    def render(template: str, macro: str, **context: Any) -> str:
        """Calls `macro` of `templates/<template>.html.j2` with `context` as keyword arguments."""
        module = Templates._environment().get_template(f"{template}.html.j2").module
        return str(getattr(module, macro)(**context))

    @staticmethod
    @cache
    def _environment() -> Environment:
        environment = Environment(
            loader=PackageLoader("smart_home_agent.ui.components", "templates"),
            autoescape=True,
            undefined=StrictUndefined,
            extensions=[CompactSource],
        )
        environment.filters.update(
            price=Markup.price,
            safe_url=Markup.safe_url,
            markdown_literal=lambda value: markupsafe.Markup(Markup.markdown_literal(value)),
            status_text=STATUS_TEXT.get,
            overall_text=OVERALL_TEXT.get,
        )
        return environment
