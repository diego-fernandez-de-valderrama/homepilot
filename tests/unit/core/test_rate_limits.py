from typing import Any

import pytest
from google.genai import errors, types
from pydantic import SecretStr

from catalog_ingestion.core import (
    GeminiCancelledError,
    GeminiClient,
    GeminiModelNotFoundError,
    GeminiSettings,
    QuotaExhaustedError,
)
from catalog_ingestion.core.gemini._api_errors import ApiErrors
from catalog_ingestion.core.gemini._rate_limiter import RateLimiter


def _quota_error_payload(quota_id: str) -> dict[str, Any]:
    """Shape of the 429 a real run hit on the free tier (15 requests per minute)."""
    return {
        "error": {
            "code": 429,
            "message": "You exceeded your current quota ... limit: 15, model: gemini-3.5-flash-lite\n"
            "Please retry in 27.9094719s.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {"@type": "type.googleapis.com/google.rpc.Help", "links": []},
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                            "quotaId": quota_id,
                            "quotaValue": "15",
                        }
                    ],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "27s"},
            ],
        }
    }


PER_MINUTE_429 = _quota_error_payload("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")
PER_DAY_429 = _quota_error_payload("GenerateRequestsPerDayPerProjectPerModel-FreeTier")


def test_rate_limiter_spaces_requests():
    now = [0.0]
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(30, clock=lambda: now[0], sleep=sleep)  # one request every 2 s
    for _ in range(3):
        limiter.acquire()
    assert sleeps == [2.0, 2.0]


def test_rate_limiter_disabled():
    limiter = RateLimiter(None, sleep=lambda _: pytest.fail("must not sleep"))
    limiter.acquire()


def test_error_interpretation():
    per_minute = errors.ClientError(429, PER_MINUTE_429)
    assert ApiErrors.retry_delay_seconds(per_minute) == 27.0
    assert not ApiErrors.is_daily_quota(per_minute)
    assert ApiErrors.is_retryable(per_minute)

    per_day = errors.ClientError(429, PER_DAY_429)
    assert ApiErrors.is_daily_quota(per_day)
    assert not ApiErrors.is_retryable(per_day)

    message_only = errors.ClientError(429, {"error": {"code": 429, "message": "Please retry in 3.5s."}})
    assert ApiErrors.retry_delay_seconds(message_only) == 3.5
    assert not ApiErrors.is_retryable(errors.ClientError(400, {"error": {"code": 400, "message": "bad"}}))


def _client(monkeypatch, failures: list[Exception]) -> tuple[GeminiClient, list[float], list[int]]:
    sleeps: list[float] = []
    calls: list[int] = []
    settings = GeminiSettings(_env_file=None, api_key=SecretStr("test"), max_retries=5)
    client = GeminiClient(settings, sleep=sleeps.append)

    def generate_content(**_kwargs):
        calls.append(1)
        if failures:
            raise failures.pop(0)
        return types.GenerateContentResponse()

    monkeypatch.setattr(client._client.models, "generate_content", generate_content)
    return client, sleeps, calls


def test_client_waits_the_delay_the_api_asks_for(monkeypatch):
    failures: list[Exception] = [errors.ClientError(429, PER_MINUTE_429), errors.ClientError(429, PER_MINUTE_429)]
    client, sleeps, calls = _client(monkeypatch, failures)
    client.generate("x", types.GenerateContentConfig())
    assert len(calls) == 3
    assert len(sleeps) == 2 and all(27.0 <= s <= 29.0 for s in sleeps)


def test_daily_quota_fails_fast(monkeypatch):
    client, sleeps, calls = _client(monkeypatch, [errors.ClientError(429, PER_DAY_429)])
    with pytest.raises(QuotaExhaustedError):
        client.generate("x", types.GenerateContentConfig())
    assert len(calls) == 1 and sleeps == []


def test_quota_violations_name_the_quota():
    assert ApiErrors.quota_violations(errors.ClientError(429, PER_MINUTE_429)) == [
        "GenerateRequestsPerMinutePerProjectPerModel-FreeTier=15"
    ]


def test_cancel_wakes_up_waiting_retries(monkeypatch):
    settings = GeminiSettings(_env_file=None, api_key=SecretStr("test"))
    client = GeminiClient(settings)  # default, interruptible sleep

    def generate_content(**_kwargs):
        raise errors.ClientError(429, PER_MINUTE_429)

    monkeypatch.setattr(client._client.models, "generate_content", generate_content)
    client.cancel()
    with pytest.raises(GeminiCancelledError):
        client.generate("x", types.GenerateContentConfig())  # would otherwise wait ~27 s


def test_unknown_model_fails_fast(monkeypatch):
    settings = GeminiSettings(_env_file=None, api_key=SecretStr("test"), model="gemini-typo")
    client = GeminiClient(settings)

    def get(model: str):
        if model == "gemini-typo":
            raise errors.ClientError(404, {"error": {"code": 404, "message": "not found"}})
        return types.Model(name=model)

    monkeypatch.setattr(client._client.models, "get", get)
    with pytest.raises(GeminiModelNotFoundError, match="GEMINI_MODEL='gemini-typo'"):
        client.check_models()
