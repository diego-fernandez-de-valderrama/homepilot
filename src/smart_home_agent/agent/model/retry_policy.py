from dataclasses import dataclass

from google.genai import types


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff shared by the empty-answer retries and the genai client's HTTP retries."""

    retries: int
    initial_delay: float
    max_delay: float

    def delay(self, attempt: int) -> float:
        """Delay before retry number `attempt` (0-based): initial, 2x, 4x ..., capped."""
        return min(self.initial_delay * 2**attempt, self.max_delay)

    def http_options(self) -> types.HttpRetryOptions:
        """Same backoff for transient HTTP errors (the genai client's default status codes: 408, 429, 5xx)."""
        return types.HttpRetryOptions(
            attempts=self.retries + 1, initial_delay=self.initial_delay, max_delay=self.max_delay, exp_base=2.0
        )
