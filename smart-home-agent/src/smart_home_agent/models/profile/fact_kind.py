from enum import StrEnum


class FactKind(StrEnum):
    NAME = "name"
    LANGUAGE = "language"
    ECOSYSTEM = "ecosystem"  # ecosystems and voice assistants the customer uses (canonical ids)
    HUB = "hub"  # bridges, hubs, gateways, access points, connectors (canonical hub id when it maps safely)
    OWNED_DEVICE = "owned_device"  # other smart home hardware the customer owns, in their wording
    PREFERENCE = "preference"  # lasting preferences, free text

    @property
    def is_single_valued(self) -> bool:
        """One value at a time: a new fact of this kind supersedes the previous one."""
        return self in (FactKind.NAME, FactKind.LANGUAGE)
