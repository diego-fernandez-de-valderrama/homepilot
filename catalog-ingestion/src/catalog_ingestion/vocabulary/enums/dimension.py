from enum import StrEnum


class Dimension(StrEnum):
    ECOSYSTEM = "ecosystem"  # platforms and interoperability standards (Matter, HomeKit, Hue, ...)
    VOICE_ASSISTANT = "voice_assistant"  # Alexa, Google Assistant, Siri
    PROTOCOL = "protocol"  # transport / radio (Wi-Fi, Zigbee, Thread, ...)
    MOBILE_OS = "mobile_os"  # iOS, Android
    CONTROL = "control"  # other control channels that have no canonical meaning (apps, remotes)
