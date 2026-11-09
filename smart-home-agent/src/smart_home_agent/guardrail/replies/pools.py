"""Reply texts: a small pool of equivalent variants per response type and language, so repeated blocks do not
sound canned."""

from smart_home_agent.guardrail.replies.response_type import ResponseType

DEFAULT_LANGUAGE = "en"

RESPONSES: dict[ResponseType, dict[str, tuple[str, ...]]] = {
    ResponseType.ELECTRICAL: {
        "en": (
            "I can't provide instructions for electrical wiring or mains installation. "
            "I can help you choose a compatible smart-home product or compare products instead.",
            "Wiring and connecting devices to mains voltage must be done by a qualified electrician, so I can't "
            "give instructions for that. I'm happy to help you find a suitable product or compare options.",
            "For safety reasons I don't give wiring or electrical installation instructions: please have a "
            "qualified electrician do that part. I can check which products fit your setup or compare them.",
            "Electrical installation work (wiring, terminals, mains connection) belongs in the hands of a "
            "qualified electrician, so I can't walk you through it. Shall I help you pick the right product?",
        ),
        "de": (
            "Ich kann keine Anleitungen für elektrische Verkabelung oder den Anschluss ans Stromnetz geben. "
            "Gerne helfe ich dir stattdessen, ein kompatibles Smart-Home-Produkt auszuwählen oder Produkte "
            "zu vergleichen.",
            "Verkabelung und Arbeiten an Netzspannung gehören in die Hände einer Elektrofachkraft, daher kann "
            "ich dazu keine Anleitung geben. Ich helfe dir aber gerne, ein passendes Produkt zu finden.",
            "Aus Sicherheitsgründen gebe ich keine Anleitungen zur Elektroinstallation: Bitte lass das eine "
            "Elektrofachkraft erledigen. Ich kann prüfen, welche Produkte zu deinem System passen.",
            "Anschluss und Verdrahtung am Stromnetz sollte eine Elektrofachkraft übernehmen, dafür kann ich "
            "keine Schritte erklären. Soll ich dir bei der Produktauswahl oder einem Vergleich helfen?",
        ),
    },
    ResponseType.OFF_TOPIC: {
        "en": (
            "I can help with smart-home products, compatibility, comparisons and recommendations. "
            "What are you looking for?",
            "That's outside what I can help with: I'm your smart-home advisor. Are you looking for a "
            "thermostat, lighting, a camera or something else for your home?",
            "I'm focused on smart-home products, so I can't help with that. Tell me about your home setup "
            "and I'll find compatible products for you.",
            "I can only help with smart-home topics, such as finding products, checking compatibility or "
            "comparing devices. What would you like to automate at home?",
        ),
        "de": (
            "Ich helfe dir gerne bei Smart-Home-Produkten, Kompatibilität, Vergleichen und Empfehlungen. "
            "Wonach suchst du?",
            "Dabei kann ich leider nicht helfen, ich bin dein Smart-Home-Berater. Suchst du ein Thermostat, "
            "Beleuchtung, eine Kamera oder etwas anderes für dein Zuhause?",
            "Ich konzentriere mich auf Smart-Home-Produkte und kann dazu leider nichts sagen. Erzähl mir von "
            "deinem Zuhause, dann finde ich passende Produkte für dich.",
            "Ich kann nur bei Smart-Home-Themen helfen, zum Beispiel Produkte finden, Kompatibilität prüfen "
            "oder Geräte vergleichen. Was möchtest du zu Hause automatisieren?",
        ),
    },
    ResponseType.PROMPT_INJECTION: {
        "en": (
            "I can't provide internal instructions or system configuration. "
            "I can help with smart-home products and compatibility instead.",
            "I can't share or change my internal setup. If you're looking for a smart-home product or want "
            "to check compatibility, I'm happy to help.",
            "My configuration and internal instructions aren't something I can share. Let's find the right "
            "smart-home device for you instead: what do you have in mind?",
            "I can't do that, but I can help you choose, compare or check the compatibility of smart-home products.",
        ),
        "de": (
            "Interne Anweisungen oder Systemkonfigurationen kann ich nicht herausgeben. "
            "Ich helfe dir aber gerne bei Smart-Home-Produkten und Kompatibilität.",
            "Meine interne Konfiguration kann ich weder teilen noch ändern. Wenn du ein Smart-Home-Produkt "
            "suchst oder Kompatibilität prüfen möchtest, helfe ich gerne.",
            "Interne Anweisungen und Einstellungen gebe ich nicht weiter. Lass uns lieber das passende "
            "Smart-Home-Gerät für dich finden: Woran hast du gedacht?",
            "Das kann ich nicht tun, aber ich helfe dir gerne beim Auswählen, Vergleichen oder bei der "
            "Kompatibilitätsprüfung von Smart-Home-Produkten.",
        ),
    },
    ResponseType.OUTPUT_FALLBACK: {
        "en": (
            "I couldn't verify that answer against our catalog, so I'd rather not give it. Could you tell me "
            "which product or which system (for example Alexa, Google Home or HomeKit) you're asking about?",
            "Sorry, I can't confirm that from the catalog data. Can you rephrase your question or name the "
            "product you mean?",
            "I'd rather not answer that without catalog evidence. Which product or ecosystem should I check for you?",
        ),
        "de": (
            "Diese Antwort konnte ich nicht anhand unseres Katalogs überprüfen, daher gebe ich sie lieber "
            "nicht. Um welches Produkt oder welches System (zum Beispiel Alexa, Google Home oder HomeKit) "
            "geht es dir?",
            "Das kann ich anhand der Katalogdaten leider nicht bestätigen. Kannst du die Frage umformulieren "
            "oder das Produkt nennen?",
            "Ohne Belege aus dem Katalog möchte ich das lieber nicht beantworten. Welches Produkt oder "
            "welches System soll ich für dich prüfen?",
        ),
    },
}
