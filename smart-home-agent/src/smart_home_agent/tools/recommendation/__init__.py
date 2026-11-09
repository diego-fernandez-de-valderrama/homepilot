"""The main recommendation tool (`recommend_products`): the full pipeline of `RecommendationService`, with the
session's budget, ecosystems and owned hubs as defaults."""

from smart_home_agent.tools.recommendation.recommend_products_tool import RecommendProductsTool

__all__ = ["RecommendProductsTool"]
