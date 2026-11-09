from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RawProduct:
    """One product exactly as found in products.zip (no cleaning applied)."""

    id: str
    title: str
    subtitle: str
    price: str
    variants: tuple[str, ...]
    description: str
    attributes: str
    image: str
    url: str
    original: Mapping[str, Any] = field(repr=False, compare=False)
