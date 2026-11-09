from typing import Any

from smart_home_agent.models import MAX_QUANTITY


def parse_quantity(value: Any, default: int | None) -> int | None:
    """`default` when `value` is None, else an int in 1..MAX_QUANTITY (raises ValueError otherwise)."""
    if value is None:
        return default
    quantity = int(value)
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"quantity must be between 1 and {MAX_QUANTITY}.")
    return quantity
