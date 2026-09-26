"""Versioned prompt for catalog enrichment. Bump PROMPT_VERSION on any change so cached
LLM outputs are recomputed."""

from catalog_ingestion.domain.enrichment import WebPage
from catalog_ingestion.domain.facts import CompatibilityFact, Requirement
from catalog_ingestion.domain.product import NormalizedProduct
from catalog_ingestion.vocabulary.categories import CATEGORIES

PROMPT_VERSION = "2026-09-26.1"

SYSTEM_INSTRUCTION = """You structure product data for a smart home retailer's catalog.
You receive the retailer's catalog entry (German) and, sometimes, the text of the product page.

Hard rules:
1. Use ONLY the provided sources. Never use prior knowledge about the brand or model.
2. Never guess. If a source does not state something, leave it out. Missing information is
   "unknown", which is represented by NOT emitting a claim. Never turn "not mentioned" into
   "unsupported", and never into "supported".
3. Every compatibility claim and requirement needs `evidence_quote`: a short verbatim substring
   copied character-for-character from the cited source (`catalog` or `web`). Claims whose quote
   cannot be found in the source are discarded.
4. Keep concepts separate:
   - Apple Siri (voice assistant) is NOT Apple HomeKit / Apple Home (ecosystem).
   - Google Assistant (voice assistant) is NOT Google Home (ecosystem).
   - Amazon Alexa is a voice assistant.
   - Matter is an ecosystem/standard, NOT a protocol, and NOT the same as Wi-Fi or Thread.
   - Protocols are transports: Wi-Fi (WLAN), Zigbee, Z-Wave, Bluetooth, Thread, Ethernet, DECT,
     proprietary radio ("Funk", e.g. 868 MHz).
5. `unsupported` only when a source explicitly says something does not work
   (e.g. "nicht kompatibel mit ...").
6. Requirements are things the buyer needs in addition to the product (hub, gateway, bridge,
   subscription, Wi-Fi network, professional electrician). Use `alternatives` when the source
   says any one of several options works.
7. key_features and use_cases are short English phrases. Use cases may describe what the product
   is typically used for given its stated type and features, but must not add capabilities.
8. Summaries: factual, no marketing superlatives, no claims beyond the sources.
"""


def _category_list() -> str:
    return "\n".join(f"- {c.key}: {c.label_en}" for c in CATEGORIES)


def _catalog_block(product: NormalizedProduct) -> str:
    lines = [f"Title: {product.title}"]
    if product.subtitle:
        lines.append(f"Subtitle: {product.subtitle}")
    if product.variants:
        lines.append(f"Variants: {', '.join(product.variants)}")
    if product.category_slug:
        lines.append(f"Shop category (URL slug): {product.category_slug}")
    lines.append(f"Price: {product.price.raw.strip()}")
    if product.description.highlights:
        lines.append("Highlights:")
        lines.extend(f"- {line}" for line in product.description.highlights)
    if product.description.text:
        lines.append("Description:")
        lines.append(product.description.text)
    if product.attributes.badges:
        lines.append(f"Badges: {', '.join(product.attributes.badges)}")
    if product.attributes.entries:
        lines.append("Attributes:")
        section = None
        for entry in product.attributes.entries:
            if entry.section != section:
                section = entry.section
                lines.append(f"[{section}]")
            lines.append(f"{entry.key}: {entry.value}")
    return "\n".join(lines)


def _known_facts_block(facts: tuple[CompatibilityFact, ...], requirements: tuple[Requirement, ...]) -> str:
    if not facts and not requirements:
        return "(none)"
    lines = [f"- {fact.dimension.value}: {fact.raw_value} ({fact.status.value})" for fact in facts]
    lines.extend(f"- requirement: {req.item} ({req.necessity.value})" for req in requirements)
    return "\n".join(lines)


def build_prompt(
    product: NormalizedProduct,
    facts: tuple[CompatibilityFact, ...],
    requirements: tuple[Requirement, ...],
    web_page: WebPage | None,
) -> str:
    web_block = f"URL: {web_page.url}\n{web_page.text}" if web_page is not None and web_page.ok else "(not available)"
    return f"""Structure this product.

Allowed category keys:
{_category_list()}

## SOURCE: catalog
{_catalog_block(product)}

## SOURCE: web
{web_block}

## Facts already extracted deterministically from the catalog attributes
You do not need to repeat these, but add any other compatibility claims or requirements
stated in the description, title, subtitle or web source.
{_known_facts_block(facts, requirements)}
"""
