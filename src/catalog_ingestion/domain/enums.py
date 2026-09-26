"""Enumerations shared by domain models and boundary schemas."""

from enum import StrEnum


class FactStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class FactSource(StrEnum):
    """Where the evidence for a fact was found."""

    CATALOG = "catalog"  # the original JSON from products.zip
    WEB = "web"  # the product page referenced by the dataset URL
    LLM = "llm"  # derived by the LLM without a verbatim quote (descriptive fields only)


class Method(StrEnum):
    """How a fact was produced from its source."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"


class Dimension(StrEnum):
    ECOSYSTEM = "ecosystem"  # platforms and interoperability standards (Matter, HomeKit, Hue, ...)
    VOICE_ASSISTANT = "voice_assistant"  # Alexa, Google Assistant, Siri
    PROTOCOL = "protocol"  # transport / radio (Wi-Fi, Zigbee, Thread, ...)
    MOBILE_OS = "mobile_os"  # iOS, Android
    CONTROL = "control"  # other control channels that have no canonical meaning (apps, remotes)


class RequirementKind(StrEnum):
    HUB = "hub"
    GATEWAY = "gateway"
    APP = "app"
    SUBSCRIPTION = "subscription"
    NETWORK = "network"
    DEVICE = "device"
    PROFESSIONAL_INSTALLATION = "professional_installation"
    OTHER = "other"


class Necessity(StrEnum):
    REQUIRED = "required"
    REQUIRED_FOR_SOME_FEATURES = "required_for_some_features"


class WebStatus(StrEnum):
    NOT_NEEDED = "not_needed"
    SKIPPED = "skipped"
    OK = "ok"
    FAILED = "failed"


class CompletenessLevel(StrEnum):
    RICH = "rich"
    PARTIAL = "partial"
    SPARSE = "sparse"
