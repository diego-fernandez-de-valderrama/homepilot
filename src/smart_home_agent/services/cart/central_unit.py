import re

from smart_home_agent.models import ProductSummary

# Matched against the product type (the title only when the type is missing). Plain "controller" is not enough:
# RGBW, dimmer and underfloor heating controllers are per-room devices.
_CENTRAL_UNIT = re.compile(
    r"\b(hub|gateway|bridge|access point|base station|basisstation|zentrale|ccu\d*|control cent(?:er|re)"
    r"|central control unit|smart home control(?:ler| unit)|starter[ -]?(?:set|kit)|starterkit)\b",
    re.IGNORECASE,
)


class CentralUnit:
    """A central unit (hub, gateway, bridge, access point, control centre, smart home controller, starter set) runs
    every device of a home, so more than one of it in the cart is a likely mistake ("control 6 windows" is not 6
    controllers)."""

    @staticmethod
    def matches(product: ProductSummary) -> bool:
        return _CENTRAL_UNIT.search(product.product_type or product.title) is not None
