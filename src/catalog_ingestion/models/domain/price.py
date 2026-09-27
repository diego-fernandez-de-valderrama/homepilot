from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Price:
    value: Decimal | None
    currency: str | None
    original_value: Decimal | None = None
    savings: Decimal | None = None
    raw: str = ""
