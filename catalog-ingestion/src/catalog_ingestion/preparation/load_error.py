from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoadError:
    member: str
    error: str
    duplicate: bool = False  # the product itself was loaded from another member
