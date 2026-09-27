class GeminiCancelledError(RuntimeError):
    """Raised in worker threads when the run is cancelled (Ctrl-C) during a wait."""
