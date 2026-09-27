"""Fixed customer-facing texts of the HTML components (English UI; the failure notice is localized)."""

from catalog_ingestion.vocabulary import FactStatus

LANGUAGES = {"en": "English", "de": "Deutsch"}

# Customer wording per status: "unknown" is "not confirmed", never "compatible" or "incompatible".
STATUS_TEXT = {
    FactStatus.SUPPORTED: "Supported",
    FactStatus.UNKNOWN: "Not confirmed",
    FactStatus.UNSUPPORTED: "Not supported",
}
OVERALL_TEXT = {
    FactStatus.SUPPORTED: "Works with your setup",
    FactStatus.UNKNOWN: "Not confirmed for your setup",
    FactStatus.UNSUPPORTED: "Not compatible with your setup",
}
REQUIREMENT_TEXT = {"satisfied": "you have it", "missing": "not in your setup", "unverified": "check if you have it"}

CONFIRM_STATE_TEXT = {
    ("add", "confirmed"): "Added to your cart",
    ("remove", "confirmed"): "Removed from your cart",
    ("add", "cancelled"): "Not added",
    ("remove", "cancelled"): "Not removed",
}

FAILURE_TEXT = {
    "en": ("Sorry, I couldn't finish my answer.", "Please send your message again in a moment."),
    "de": (
        "Entschuldigung, ich konnte meine Antwort nicht fertigstellen.",
        "Bitte senden Sie Ihre Nachricht gleich noch einmal.",
    ),
}

# Progress labels per tool. Shown only once the model really calls that tool in the current turn.
TOOL_LABELS = {
    "recommend_products": "Finding matching products in the catalog",
    "search_products": "Searching the catalog",
    "filter_products": "Filtering the catalog",
    "get_product": "Loading product details",
    "check_compatibility": "Checking compatibility",
    "compare_products": "Comparing products",
    "get_evidence": "Looking up the sources",
    "remember_preferences": "Noting your preferences",
    "remember_customer_facts": "Remembering what you told me",
    "view_cart": "Checking your cart",
    "add_to_cart": "Preparing the change to your cart",
    "remove_from_cart": "Preparing the change to your cart",
}
