"""Resolves the presentation tags of an answer to catalog data (PostgreSQL only).

A tag whose data cannot be resolved (unknown id, a comparison of fewer than two known products, an
upgrade that is not the recommender's upsell) gets no entry, and the UI then drops or degrades it.
"""

from smart_home_agent.services.rich_content.rich_content_service import RichContentService

__all__ = ["RichContentService"]
