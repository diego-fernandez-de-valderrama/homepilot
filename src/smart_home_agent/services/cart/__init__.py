"""Shopping cart operations over the session's cart items. Pure list updates plus one catalog read per view:
prices and titles always come from PostgreSQL, never from the session.

One add/remove call can cover several products. It is applied all or nothing: the customer confirmed the
whole change, so a change with any invalid product leaves the cart untouched and reports every problem
(`CartChangeError`).

A central unit (`CentralUnit`) runs every device of a home, so an add that would put more than one of it into
the cart is a likely mistake: `CartService.central_units_over_one` finds them, and the add tool asks the customer
first."""

from smart_home_agent.services.cart.cart_change_error import CartChangeError
from smart_home_agent.services.cart.cart_service import CartService
from smart_home_agent.services.cart.central_unit import CentralUnit
from smart_home_agent.services.cart.not_in_cart_error import NotInCartError

__all__ = ["CartChangeError", "CartService", "CentralUnit", "NotInCartError"]
