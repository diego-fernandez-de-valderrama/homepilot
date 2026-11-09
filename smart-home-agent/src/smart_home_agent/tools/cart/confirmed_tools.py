from smart_home_agent.models import CartAction

# The cart tools that wait for the customer's confirmation in the interface, with the cart action they apply.
CONFIRMED_TOOLS: dict[str, CartAction] = {"add_to_cart": "add", "remove_from_cart": "remove"}
