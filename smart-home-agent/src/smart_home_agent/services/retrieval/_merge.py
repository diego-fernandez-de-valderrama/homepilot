from smart_home_agent.models import SearchCandidate


def merge(*groups: list[SearchCandidate]) -> dict[str, float | None]:
    """product id -> best semantic score (None when only the structured path found it)."""
    merged: dict[str, float | None] = {}
    for group in groups:
        for candidate in group:
            current = merged.get(candidate.product_id)
            if candidate.score is not None and (current is None or candidate.score > current):
                merged[candidate.product_id] = candidate.score
            else:
                merged.setdefault(candidate.product_id, current)
    return merged
