"""Catalog data for the presentation tags of one answer (the tags themselves are parsed by `answer_tags`).

A tag only says what to show: every value in `RichContent` is resolved from PostgreSQL, never taken from the
model's text.
"""

from smart_home_agent.models.rich_content.product_compatibility import ProductCompatibility
from smart_home_agent.models.rich_content.rich_content import RichContent

__all__ = ["ProductCompatibility", "RichContent"]
