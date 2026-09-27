"""Which catalog products are the bare hub for a canonical requirement id (title keywords, no bundles)."""

from collections.abc import Sequence

from smart_home_agent.models import Product

HUB_CATEGORY = "hub_gateway"

# canonical requirement id -> keywords that must all appear in the hub product's title (case-insensitive)
HUB_TITLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "homematic_ip_access_point": ("homematic", "access point"),
    "homematic_ccu3": ("homematic", "ccu3"),
    "bosch_smart_home_controller": ("bosch", "smart home controller"),
    "philips_hue_bridge": ("hue", "bridge"),
    "gardena_smart_gateway": ("gardena", "gateway"),
    "ring_alarm_base_station": ("ring", "basisstation"),
}
_BUNDLE_WORDS = ("set",)  # "Starter-Set", "Set": bundles with other devices are not the bare hub


def is_bare_hub(product: Product, keywords: Sequence[str]) -> bool:
    title = product.title.casefold()
    words = set(title.replace("-", " ").split())
    return all(k in title for k in keywords) and not words & set(_BUNDLE_WORDS)
