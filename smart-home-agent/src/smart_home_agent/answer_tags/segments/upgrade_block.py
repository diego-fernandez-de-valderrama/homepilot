from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UpgradeBlock:
    from_id: str
    to_id: str
