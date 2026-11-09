import threading
from collections.abc import Callable

from google import genai
from google.genai import errors, types
from tenacity import Retrying, retry_if_exception, stop_after_attempt

from catalog_ingestion.core.gemini._api_errors import ApiErrors
from catalog_ingestion.core.gemini._rate_limiter import RateLimiter
from catalog_ingestion.core.gemini._retry_schedule import RetrySchedule
from catalog_ingestion.core.gemini.gemini_cancelled_error import GeminiCancelledError
from catalog_ingestion.core.gemini.gemini_model_not_found_error import GeminiModelNotFoundError
from catalog_ingestion.core.gemini.gemini_not_configured_error import GeminiNotConfiguredError
from catalog_ingestion.core.gemini.quota_exhausted_error import QuotaExhaustedError
from catalog_ingestion.core.settings import GeminiSettings


class GeminiClient:
    """Thin wrapper around google-genai with pacing and retries for rate limits and server errors."""

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
            retry=retry_if_exception(ApiErrors.is_retryable),
            wait=RetrySchedule.wait,
            stop=stop_after_attempt(settings.max_retries),
            before_sleep=RetrySchedule.log_retry,
            sleep=sleep,
            reraise=True,
        )

    @property
    def model(self) -> str:
        return self._settings.model

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

    def generate(self, contents: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        return self._call(
            self._generate_limiter,
            lambda: self._client.models.generate_content(
                model=self._settings.model,
                contents=contents,
                config=GeminiClient.without_automatic_function_calling(config),
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

    @staticmethod
    def without_automatic_function_calling(config: types.GenerateContentConfig) -> types.GenerateContentConfig:
        """google-genai enables automatic function calling (AFC) by default and warns about it.

        This pipeline never uses function calling (only structured output and the url_context tool),
        so AFC is disabled explicitly unless a caller configured it.
        """
        if config.automatic_function_calling is not None:
            return config
        return config.model_copy(
            update={"automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)}
        )

    def _interruptible_sleep(self, seconds: float) -> None:
        if self._cancelled.wait(seconds):
            raise GeminiCancelledError("run cancelled")

    def _call[T](self, limiter: RateLimiter, request: Callable[[], T]) -> T:
        def attempt() -> T:
            limiter.acquire()
            return request()

        try:
            return self._retrying(attempt)
        except errors.APIError as exc:
            if ApiErrors.is_daily_quota(exc):
                raise QuotaExhaustedError(f"Gemini daily quota exhausted: {exc.message}") from exc
            raise
