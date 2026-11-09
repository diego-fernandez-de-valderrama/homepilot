from catalog_ingestion.vocabulary.compatibility_term import CompatibilityTerm
from catalog_ingestion.vocabulary.enums import Dimension

TERMS: tuple[CompatibilityTerm, ...] = (
    # Ecosystems, platforms and interoperability standards
    CompatibilityTerm("matter", Dimension.ECOSYSTEM, "Matter", ("matter", "[+m] matter")),
    CompatibilityTerm(
        "apple_home",
        Dimension.ECOSYSTEM,
        "Apple Home (HomeKit)",
        (
            "apple homekit",
            "apple homekit system",
            "homekit",
            "apple home",
            "apple home-kit",
            "apple home-kit®",
            "sprachsteuerung per apple homekit",
        ),
    ),
    CompatibilityTerm(
        "google_home", Dimension.ECOSYSTEM, "Google Home", ("google home", "googlehome", "google home app")
    ),
    CompatibilityTerm("google_nest", Dimension.ECOSYSTEM, "Google Nest", ("nest smart home system", "google nest")),
    CompatibilityTerm(
        "samsung_smartthings",
        Dimension.ECOSYSTEM,
        "Samsung SmartThings",
        ("samsung smartthings", "samsung smart things", "samsung smart things system", "smartthings"),
    ),
    CompatibilityTerm(
        "bosch_smart_home",
        Dimension.ECOSYSTEM,
        "Bosch Smart Home",
        ("bosch smart home", "bosch smart home system", "bosch smart home app"),
    ),
    CompatibilityTerm(
        "homematic_ip",
        Dimension.ECOSYSTEM,
        "Homematic IP",
        ("homematic ip", "homematic ip system", "homematic ip app"),
    ),
    CompatibilityTerm(
        "philips_hue",
        Dimension.ECOSYSTEM,
        "Philips Hue",
        (
            "philips hue",
            "philips hue system",
            "philips hue app",
            "app philips hue",
            "philips hue bluetooth app",
            "philips hue bridge",
        ),
    ),
    CompatibilityTerm(
        "ledvance_smart_plus",
        Dimension.ECOSYSTEM,
        "LEDVANCE SMART+",
        ("ledvance smart+", "ledvance smart+ system", "ledvance smart+ app", "ledvance smart+ wifi app"),
    ),
    CompatibilityTerm("ring", Dimension.ECOSYSTEM, "Ring", ("ring smart home system", "ring app")),
    CompatibilityTerm(
        "abus_smartvest", Dimension.ECOSYSTEM, "ABUS Smartvest", ("abus smartvest system", "smartvest pro-app")
    ),
    CompatibilityTerm(
        "smart_friends",
        Dimension.ECOSYSTEM,
        "Smart Friends",
        ("abus smart friends system", "smart friends system", "smart friends", "smart friends app"),
    ),
    CompatibilityTerm(
        "schellenberg_smart_home",
        Dimension.ECOSYSTEM,
        "Schellenberg Smart Home",
        ("schellenberg smart home system", "schellenberg smart home"),
    ),
    CompatibilityTerm(
        "gardena_smart_system",
        Dimension.ECOSYSTEM,
        "Gardena smart system",
        ("gardena smart system", "gardena smart gateway", "gardena smart"),
    ),
    CompatibilityTerm(
        "magenta_smarthome",
        Dimension.ECOSYSTEM,
        "Magenta SmartHome",
        ("magenta smart home system", "magenta smarthome", "magenta smart home"),
    ),
    CompatibilityTerm("wiz", Dimension.ECOSYSTEM, "WiZ", ("wiz system", "wiz", "wiz app")),
    CompatibilityTerm("eglo_connect", Dimension.ECOSYSTEM, "EGLO connect", ("eglo connect system", "eglo connect")),
    CompatibilityTerm("nuki", Dimension.ECOSYSTEM, "Nuki", ("nuki smart home", "nuki app")),
    CompatibilityTerm("velux_active", Dimension.ECOSYSTEM, "VELUX Smart Home", ("velux smart home system",)),
    CompatibilityTerm("arlo", Dimension.ECOSYSTEM, "Arlo", ("arlo smart system", "arlo app")),
    CompatibilityTerm("razer_chroma", Dimension.ECOSYSTEM, "Razer Chroma", ("razer chroma system", "razer chroma")),
    CompatibilityTerm(
        "essentials_smart_home",
        Dimension.ECOSYSTEM,
        "Essentials Smart Home",
        ("essentials smart home system", "essentials smart home app"),
    ),
    CompatibilityTerm("ifttt", Dimension.ECOSYSTEM, "IFTTT", ("ifttt", "ifttt system")),
    CompatibilityTerm("aqara_home", Dimension.ECOSYSTEM, "Aqara Home", ("aqara home",)),
    CompatibilityTerm(
        "tuya_smart_life",
        Dimension.ECOSYSTEM,
        "Tuya / Smart Life",
        ("tuya app", "smart life app", "tuya smart", "tuya smart app"),
    ),
    CompatibilityTerm("xiaomi_home", Dimension.ECOSYSTEM, "Xiaomi Home", ("mi home app", "xiaomi home", "mi home")),
    CompatibilityTerm(
        "shelly", Dimension.ECOSYSTEM, "Shelly", ("shelly cloud app", "shelly smart control app", "shelly app")
    ),
    # Voice assistants
    CompatibilityTerm(
        "amazon_alexa",
        Dimension.VOICE_ASSISTANT,
        "Amazon Alexa",
        (
            "amazon alexa",
            "alexa",
            "amazon alexa möglich",
            "amazon echo + app",
            "amazon echo dot + app",
            "amazon echo show + app",
            "amazon echo plus + app",
            "amazon echo",
            "amazon echo dot",
            "amazon echo show",
            "amazon echo plus",
        ),
    ),
    CompatibilityTerm("google_assistant", Dimension.VOICE_ASSISTANT, "Google Assistant", ("google assistant",)),
    CompatibilityTerm("apple_siri", Dimension.VOICE_ASSISTANT, "Apple Siri", ("apple siri", "siri")),
    # Transport protocols
    CompatibilityTerm("wifi", Dimension.PROTOCOL, "Wi-Fi", ("wlan", "wifi", "wi-fi", "w-lan")),
    CompatibilityTerm("zigbee", Dimension.PROTOCOL, "Zigbee", ("zigbee", "zigbee 3.0")),
    CompatibilityTerm("z_wave", Dimension.PROTOCOL, "Z-Wave", ("z-wave", "z-wave plus", "zwave")),
    CompatibilityTerm(
        "bluetooth", Dimension.PROTOCOL, "Bluetooth", ("bluetooth", "bluetooth le", "bluetooth low energy")
    ),
    CompatibilityTerm("thread", Dimension.PROTOCOL, "Thread", ("thread",)),
    CompatibilityTerm("ethernet", Dimension.PROTOCOL, "Ethernet (LAN)", ("lan", "ethernet")),
    CompatibilityTerm("dect", Dimension.PROTOCOL, "DECT", ("dect", "dect ule")),
    CompatibilityTerm("io_homecontrol", Dimension.PROTOCOL, "io-homecontrol", ("io-homecontrol",)),
    CompatibilityTerm("proprietary_rf", Dimension.PROTOCOL, "Proprietary radio (RF)", ("funk",)),
    # Mobile operating systems (companion apps)
    CompatibilityTerm("ios", Dimension.MOBILE_OS, "iOS", ("ios", "apple ios")),
    CompatibilityTerm("android", Dimension.MOBILE_OS, "Android", ("android",)),
)

# Short base names used in running text ("HomeKit", "SmartThings", "Hue"), on top of aliases and labels.
EXTRA_SURFACE_FORMS: dict[str, tuple[str, ...]] = {
    "apple_home": ("homekit", "apple home"),
    "samsung_smartthings": ("smartthings", "smart things"),
    "philips_hue": ("hue",),
    "wifi": ("wlan", "wi-fi", "wifi"),
    "z_wave": ("z-wave", "zwave"),
    "bluetooth": ("bluetooth",),
    "proprietary_rf": ("funk", "mhz"),
    "ethernet": ("lan", "ethernet"),
    "ledvance_smart_plus": ("smart+",),
}
