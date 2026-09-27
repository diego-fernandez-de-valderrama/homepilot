class EmbeddingModelMismatchError(RuntimeError):
    """A partial run was refused: Qdrant holds points of another embedding model (run `reindex` first)."""
