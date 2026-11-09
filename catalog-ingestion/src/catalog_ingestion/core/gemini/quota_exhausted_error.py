class QuotaExhaustedError(RuntimeError):
    """A quota that does not reset within this run (e.g. requests per day). Retrying is pointless."""
