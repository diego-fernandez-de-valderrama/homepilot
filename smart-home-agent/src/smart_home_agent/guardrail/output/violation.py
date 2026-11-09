"""A failed output check."""

from typing import Literal

from pydantic import BaseModel

ViolationKind = Literal["electrical", "unknown_product", "unsupported_compatibility", "prompt_leak", "off_topic"]


class Violation(BaseModel):
    kind: ViolationKind
    detail: str
