from catalog_ingestion.vocabulary.category import Category

CATEGORIES: tuple[Category, ...] = (
    Category("smart_bulb", "Light bulb", "Leuchtmittel", ("led-lampen", "smart-home-leuchtmittel")),
    Category(
        "ceiling_light",
        "Ceiling light",
        "Deckenleuchte",
        (
            "smarte-deckenleuchten",
            "deckenlampen",
            "led-deckenlampen",
            "led-deckenlampen-rund",
            "pendelleuchten",
            "deckenstrahler",
            "smarte-deckenstrahler",
        ),
    ),
    Category("recessed_spotlight", "Recessed spotlight", "Einbaustrahler", ("einbaustrahler", "smarte-einbaustrahler")),
    Category("led_panel", "LED panel", "LED-Panel", ("smarte-led-panels", "led-panels")),
    Category(
        "led_strip",
        "LED strip and light chain",
        "LED-Streifen & Lichterkette",
        ("led-streifen", "led-lichtleisten", "lichterketten"),
    ),
    Category(
        "outdoor_light",
        "Outdoor light",
        "Außenleuchte",
        (
            "aussenwandleuchten",
            "gartenbeleuchtung",
            "gartenbeleuchtungssysteme",
            "wegeleuchten",
            "akku-aussenleuchten",
            "smart-home-aussenbeleuchtung",
        ),
    ),
    Category(
        "lamp",
        "Table, floor and wall lamp",
        "Tisch-, Steh- & Wandleuchte",
        ("tischlampen", "stehlampen", "smarte-dekolampen", "akku-tischleuchten", "wandleuchten", "smarte-wandlampen"),
    ),
    Category(
        "switch",
        "Smart switch, dimmer and relay",
        "Schalter, Dimmer & Relais",
        ("smart-home-schalter", "smart-home-lichtschalter", "dimmer", "schaltrelais"),
    ),
    Category(
        "smart_plug",
        "Smart plug and socket",
        "Steckdose & Zwischenstecker",
        ("smart-home-steckdosen", "funkschalter-funkstecker", "steckdosenleisten", "gartensteckdosen"),
    ),
    Category("remote_control", "Remote control", "Fernbedienung", ("fernbedienungen",)),
    Category("energy_monitoring", "Energy monitoring", "Energiemessung", ("energiekosten-messgeraete", "stromzaehler")),
    Category(
        "hub_gateway",
        "Hub, gateway and starter kit",
        "Zentrale, Gateway & Starter-Set",
        ("smart-home-starter-kits-gateways",),
    ),
    Category(
        "smart_speaker_display",
        "Voice assistant, smart speaker and display",
        "Sprachassistent & Smart Display",
        ("sprachassistenten-smart-home-hubs-displays",),
    ),
    Category(
        "heating_control",
        "Heating control and thermostat",
        "Heizungssteuerung & Thermostat",
        ("smart-home-thermostate", "thermostatkoepfe", "smart-home-fussbodenheizung", "fussbodenheizungszubehoer"),
    ),
    Category(
        "climate_sensor",
        "Climate and weather sensor",
        "Raumklima- & Wettersensor",
        ("smart-home-raumluftsensoren", "wetterstationen", "bodenfeuchtesensoren"),
    ),
    Category(
        "contact_sensor",
        "Door and window sensor",
        "Tür- & Fensterkontakt",
        (
            "smart-home-fensterkontakte-tuerkontakte",
            "fensteralarme-tueralarme",
            "erschuetterungssensoren",
            "fenstersicherung",
        ),
    ),
    Category("motion_sensor", "Motion sensor", "Bewegungsmelder", ("bewegungsmelder", "durchgangsmelder")),
    Category(
        "safety_detector",
        "Smoke, gas and water detector",
        "Rauch-, Gas- & Wassermelder",
        ("rauchwarnmelder-rauchmelder", "wassermelder", "smart-home-rauchwarnmelder-wassermelder", "gasmelder"),
    ),
    Category(
        "alarm_system",
        "Alarm system",
        "Alarmanlage",
        ("smart-home-alarmanlagen", "alarmsirenen", "alarmanlagenzubehoer"),
    ),
    Category(
        "security_camera",
        "Security camera",
        "Überwachungskamera",
        ("ueberwachungskameras-aussen", "ueberwachungskameras-innen", "smart-home-kameras"),
    ),
    Category(
        "doorbell_intercom",
        "Doorbell and intercom",
        "Türklingel & Sprechanlage",
        (
            "tuerklingeln-mit-kamera",
            "smart-home-tuerklingeln",
            "tuersprechanlagen",
            "tuergongs",
            "klingeltaster",
            "tuerspione",
        ),
    ),
    Category(
        "door_lock",
        "Smart lock",
        "Türschloss",
        ("smart-home-tuerschloesser", "elektrische-tuerschloesser", "vorhaengeschloesser"),
    ),
    Category(
        "shutter_blind_control",
        "Shutter, blind and awning control",
        "Rollladen-, Rollo- & Markisensteuerung",
        (
            "smart-home-rollladensteuerung",
            "rollladensteuerung",
            "rollladenmotoren",
            "rollomotoren",
            "gurtwickler",
            "rollladenzubehoer",
            "dachfensterzubehoer",
        ),
    ),
    Category(
        "garage_door", "Garage door opener", "Garagentorantrieb", ("garagentorantriebe", "garagentor-schluesseltaster")
    ),
    Category(
        "robot_mower",
        "Robotic lawn mower",
        "Mähroboter",
        ("maehroboter-mit-begrenzungskabel", "maehrobotor-mit-kamera", "maehrobotor-mit-gps"),
    ),
    Category(
        "garden_irrigation",
        "Garden irrigation and water",
        "Bewässerung & Hauswasser",
        ("bewaesserungscomputer", "sprinklersysteme", "hauswasserwerke-hauswasserautomaten"),
    ),
    Category(
        "climate_appliance",
        "Air conditioner and fan",
        "Klimagerät & Ventilator",
        ("mobile-klimageraete", "klimaanlagen", "kuechenventilatoren"),
    ),
    Category("ev_charging", "EV charging", "E-Auto-Laden", ("e-auto-ladestationen", "e-mobility")),
    Category("water_heater", "Water heater", "Warmwasserspeicher", ("warmwasserspeicher",)),
    Category("accessory", "Accessory", "Zubehör", ("verlaengerungskabel", "kabelverbinder")),
)

# Brand landing pages: the slug says nothing about the product type.
BRAND_PAGE_SLUGS: frozenset[str] = frozenset(
    {
        "homematic-ip-smart-home",
        "shelly-smart-home",
        "philips-hue-smart-home",
        "ring-smart-home",
        "xiaomi-smart-home",
        "paulmann-plug-shine",
    }
)
