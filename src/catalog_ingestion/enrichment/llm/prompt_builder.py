from typing import ClassVar

from catalog_ingestion.enrichment.llm._system_instruction import SYSTEM_INSTRUCTION
from catalog_ingestion.models import CompatibilityFact, NormalizedProduct, Requirement, WebPage
from catalog_ingestion.vocabulary import CategoryVocabulary


class PromptBuilder:
    """The versioned enrichment prompt. Bump `VERSION` on any change to it or to the system instruction,
    so cached LLM outputs are recomputed."""

    VERSION: ClassVar[str] = "2026-09-26.1"
    SYSTEM_INSTRUCTION: ClassVar[str] = SYSTEM_INSTRUCTION

    @staticmethod
    def build(
        product: NormalizedProduct,
        facts: tuple[CompatibilityFact, ...],
        requirements: tuple[Requirement, ...],
        web_page: WebPage | None,
    ) -> str:
        web_ok = web_page is not None and web_page.ok
        web_block = f"URL: {web_page.url}\n{web_page.text}" if web_ok and web_page else "(not available)"
        return f"""Structure this product.

Allowed category keys:
{PromptBuilder._category_list()}

## SOURCE: catalog
{PromptBuilder._catalog_block(product)}

## SOURCE: web
{web_block}

## Facts already extracted deterministically from the catalog attributes
You do not need to repeat these, but add any other compatibility claims or requirements
stated in the description, title, subtitle or web source.
{PromptBuilder._known_facts_block(facts, requirements)}
"""

    @staticmethod
    def _category_list() -> str:
        return "\n".join(f"- {c.key}: {c.label_en}" for c in CategoryVocabulary.CATEGORIES)

    @staticmethod
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

    @staticmethod
    def _known_facts_block(facts: tuple[CompatibilityFact, ...], requirements: tuple[Requirement, ...]) -> str:
        if not facts and not requirements:
            return "(none)"
        lines = [f"- {fact.dimension.value}: {fact.raw_value} ({fact.status.value})" for fact in facts]
        lines.extend(f"- requirement: {req.item} ({req.necessity.value})" for req in requirements)
        return "\n".join(lines)
