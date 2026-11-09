from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompatibilityBlock:
    product_id: str
