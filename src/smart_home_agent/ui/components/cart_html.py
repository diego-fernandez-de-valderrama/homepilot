from smart_home_agent.models import CartLine, CartView
from smart_home_agent.ui.components._templates import Templates


class CartHtml:
    """The cart in the customer panel (its stepper buttons are Streamlit widgets rendered below each line)."""

    @staticmethod
    def header(view: CartView) -> str:
        return Templates.render("cart", "header", view=view)

    @staticmethod
    def line(line: CartLine, missing_images: frozenset[str] = frozenset()) -> str:
        return Templates.render("cart", "line", line=line, missing_images=missing_images)

    @staticmethod
    def total(view: CartView) -> str:
        return Templates.render("cart", "total", view=view)
