"""Candidate discovery: semantic (Qdrant) and structured (PostgreSQL), merged by product id. Qdrant only finds
ids; every product is hydrated from PostgreSQL."""

from smart_home_agent.services.retrieval.retrieval_service import RetrievalService

__all__ = ["RetrievalService"]
