from enum import StrEnum


class RequirementKind(StrEnum):
    HUB = "hub"
    GATEWAY = "gateway"
    APP = "app"
    SUBSCRIPTION = "subscription"
    NETWORK = "network"
    DEVICE = "device"
    PROFESSIONAL_INSTALLATION = "professional_installation"
    OTHER = "other"
