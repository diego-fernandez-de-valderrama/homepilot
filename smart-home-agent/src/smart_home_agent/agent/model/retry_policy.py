from dataclasses import dataclass

from google.genai import types
from tenacity import wait_exponential
from tenacity.wait import wait_base


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff shared by the empty-answer retries and the genai client's HTTP retries."""

    retries: int
    initial_delay: float
    max_delay: float

    def wait(self) -> wait_base:
        """tenacity wait before each retry: initial, 2x, 4x ..., capped."""
        return wait_exponential(multiplier=self.initial_delay, max=self.max_delay, exp_base=2)

    def http_options(self) -> types.HttpRetryOptions:
        """Same backoff for transient HTTP errors (the genai client's default status codes: 408, 429, 5xx)."""
        return types.HttpRetryOptions(
            attempts=self.retries + 1, initial_delay=self.initial_delay, max_delay=self.max_delay, exp_base=2.0
        )
