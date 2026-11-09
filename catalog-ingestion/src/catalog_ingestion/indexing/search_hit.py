from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchHit:
    product_id: str
    score: float
    payload: dict
