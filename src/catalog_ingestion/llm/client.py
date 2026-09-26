"""Thin wrapper around google-genai with retries for rate limits and server errors."""

import logging
import random
import threading
from collections.abc import Callable
from typing import Protocol

from google import genai
from google.genai import errors, types
from tenacity import RetryCallState, Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from catalog_ingestion.core.logging import log_fields
from catalog_ingestion.core.settings import GeminiSettings
from catalog_ingestion.llm.errors import (
    QuotaExhaustedError,
    is_daily_quota,
    is_retryable,
    quota_violations,
    retry_delay_seconds,
)
from catalog_ingestion.llm.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_exponential = wait_exponential_jitter(initial=2, max=60)


def _wait(state: RetryCallState) -> float:
    """Honor the server's retry delay (rate limits); otherwise exponential backoff with jitter."""
    exc = state.outcome.exception() if state.outcome else None
    hint = retry_delay_seconds(exc) if exc else None
    return hint + random.uniform(0.5, 2.0) if hint is not None else _exponential(state)


def _log_retry(state: RetryCallState) -> None:
    exc = state.outcome.exception() if state.outcome else None
    wait = state.next_action.sleep if state.next_action else 0.0
    logger.info(
        "Gemini call failed, retrying",
        extra=log_fields(
            attempt=state.attempt_number,
            wait_seconds=round(wait, 1),
            error=getattr(exc, "code", exc),
            quota=quota_violations(exc) if exc else [],
        ),
    )


class TextGenerator(Protocol):
    """What the enricher and the url_context fetcher need from a Gemini client."""

    @property
    def model(self) -> str: ...

    def generate(self, contents: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse: ...


def without_automatic_function_calling(config: types.GenerateContentConfig) -> types.GenerateContentConfig:
    """google-genai enables automatic function calling (AFC) by default and warns about it.

    This pipeline never uses function calling (only structured output and the url_context tool),
    so AFC is disabled explicitly unless a caller configured it.
    """
    if config.automatic_function_calling is not None:
        return config
    return config.model_copy(update={"automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)})


class GeminiNotConfiguredError(RuntimeError):
    pass


class GeminiModelNotFoundError(RuntimeError):
    pass


class GeminiCancelledError(RuntimeError):
    """Raised in worker threads when the run is cancelled (Ctrl-C) during a wait."""


class GeminiClient:
    def __init__(self, settings: GeminiSettings, sleep: Callable[[float], None] | None = None) -> None:
        if not settings.is_configured:
            raise GeminiNotConfiguredError("GEMINI_API_KEY is not set")
        assert settings.api_key is not None
        self._settings = settings
        self._client = genai.Client(api_key=settings.api_key.get_secret_value())
        self._cancelled = threading.Event()
        sleep = sleep or self._interruptible_sleep
        # Separate limiters: generation and embedding models have separate quotas.
        self._generate_limiter = RateLimiter(settings.requests_per_minute, sleep=sleep)
        self._embed_limiter = RateLimiter(settings.embedding_requests_per_minute, sleep=sleep)
        self._retrying = Retrying(
            retry=retry_if_exception(is_retryable),
            wait=_wait,
            stop=stop_after_attempt(settings.max_retries),
            before_sleep=_log_retry,
            sleep=sleep,
            reraise=True,
        )

    @property
    def model(self) -> str:
        return self._settings.model

    def _interruptible_sleep(self, seconds: float) -> None:
        if self._cancelled.wait(seconds):
            raise GeminiCancelledError("run cancelled")

    def cancel(self) -> None:
        """Wake up every thread waiting on a rate limit or retry so the process can exit."""
        self._cancelled.set()

    def check_models(self) -> None:
        """Fail fast on a wrong model name instead of failing every product."""
        for setting, name in (
            ("GEMINI_MODEL", self._settings.model),
            ("GEMINI_EMBEDDING_MODEL", self._settings.embedding_model),
        ):
            try:
                self._client.models.get(model=name)
            except errors.ClientError as exc:
                if exc.code == 404:
                    raise GeminiModelNotFoundError(
                        f"{setting}={name!r} does not exist for this API key "
                        "(see https://ai.google.dev/gemini-api/docs/models)"
                    ) from exc
                raise

    def _call[T](self, limiter: RateLimiter, request: Callable[[], T]) -> T:
        def attempt() -> T:
            limiter.acquire()
            return request()

        try:
            return self._retrying(attempt)
        except errors.APIError as exc:
            if is_daily_quota(exc):
                raise QuotaExhaustedError(f"Gemini daily quota exhausted: {exc.message}") from exc
            raise

    def generate(self, contents: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        return self._call(
            self._generate_limiter,
            lambda: self._client.models.generate_content(
                model=self._settings.model, contents=contents, config=without_automatic_function_calling(config)
            ),
        )

    def embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        response = self._call(
            self._embed_limiter,
            lambda: self._client.models.embed_content(
                model=self._settings.embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=self._settings.embedding_dim
                ),
            ),
        )
        embeddings = response.embeddings or []
        if len(embeddings) != len(texts):
            raise RuntimeError(f"expected {len(texts)} embeddings, got {len(embeddings)}")
        return [list(embedding.values or []) for embedding in embeddings]
