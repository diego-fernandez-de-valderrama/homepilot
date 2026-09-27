class CollectionDimensionMismatchError(RuntimeError):
    """The Qdrant collection was created for another embedding dimension (`reindex --recreate` fixes it)."""
