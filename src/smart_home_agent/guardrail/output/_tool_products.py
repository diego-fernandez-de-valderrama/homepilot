"""Products that appeared in this turn's tool results."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def tool_products(tool_responses: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """id -> title of every product that appeared in this turn's tool results."""
    products: dict[str, str] = {}
    for node in _walk(list(tool_responses)):
        pid = node.get("id") or node.get("product_id")
        if isinstance(pid, str) and isinstance(node.get("title"), str):
            products[pid] = node["title"]
        elif isinstance(pid, str):
            products.setdefault(pid, "")
    return products


def _walk(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _walk(child)
