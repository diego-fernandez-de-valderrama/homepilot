from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttributeEntry:
    section: str
    key: str
    value: str
