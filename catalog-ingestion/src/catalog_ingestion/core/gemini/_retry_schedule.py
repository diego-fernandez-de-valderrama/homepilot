import logging
import random

from tenacity import RetryCallState, wait_exponential_jitter

from catalog_ingestion.core.gemini._api_errors import ApiErrors
from catalog_ingestion.core.log_setup import LogSetup

logger = logging.getLogger("catalog_ingestion.core.gemini")


class RetrySchedule:
    """tenacity hooks for Gemini calls: how long to wait before a retry, and the log line for it."""

    _exponential = wait_exponential_jitter(initial=2, max=60)

    @staticmethod
    def wait(state: RetryCallState) -> float:
        """Honor the server's retry delay (rate limits); otherwise exponential backoff with jitter."""
        exc = state.outcome.exception() if state.outcome else None
        hint = ApiErrors.retry_delay_seconds(exc) if exc else None
        return hint + random.uniform(0.5, 2.0) if hint is not None else RetrySchedule._exponential(state)

    @staticmethod
    def log_retry(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        wait = state.next_action.sleep if state.next_action else 0.0
        logger.info(
            "Gemini call failed, retrying",
            extra=LogSetup.fields(
                attempt=state.attempt_number,
                wait_seconds=round(wait, 1),
                error=getattr(exc, "code", exc),
                quota=ApiErrors.quota_violations(exc) if exc else [],
            ),
        )
