import re
from typing import Any

from google.genai import errors


class ApiErrors:
    """Interpretation of Gemini API errors (quota type, server-suggested retry delay)."""

    RETRYABLE_CODES = frozenset({408, 429, 500, 502, 503, 504})
    _RETRY_IN_MESSAGE = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.IGNORECASE)
    _DURATION = re.compile(r"^(\d+(?:\.\d+)?)s$")

    @staticmethod
    def retry_delay_seconds(exc: BaseException) -> float | None:
        """The delay the API asks for (RetryInfo.retryDelay, or "Please retry in 27.9s")."""
        if not isinstance(exc, errors.APIError):
            return None
        for item in ApiErrors._details(exc):
            if item.get("@type", "").endswith("google.rpc.RetryInfo"):
                match = ApiErrors._DURATION.match(str(item.get("retryDelay", "")))
                if match:
                    return float(match.group(1))
        match = ApiErrors._RETRY_IN_MESSAGE.search(exc.message or "")
        return float(match.group(1)) if match else None

    @staticmethod
    def is_daily_quota(exc: BaseException) -> bool:
        """True when a QuotaFailure names a per-day quota (it will not reset during the run)."""
        if not isinstance(exc, errors.APIError) or exc.code != 429:
            return False
        return any("PerDay" in str(violation.get("quotaId", "")) for violation in ApiErrors._violations(exc))

    @staticmethod
    def quota_violations(exc: BaseException) -> list[str]:
        """e.g. ["GenerateRequestsPerMinutePerProjectPerModel-FreeTier=15"], to show which quota was hit."""
        if not isinstance(exc, errors.APIError):
            return []
        return [f"{violation.get('quotaId')}={violation.get('quotaValue')}" for violation in ApiErrors._violations(exc)]

    @staticmethod
    def is_retryable(exc: BaseException) -> bool:
        return (
            isinstance(exc, errors.APIError)
            and exc.code in ApiErrors.RETRYABLE_CODES
            and not ApiErrors.is_daily_quota(exc)
        )

    @staticmethod
    def _details(exc: errors.APIError) -> list[dict[str, Any]]:
        payload = exc.details if isinstance(exc.details, dict) else {}
        error = payload.get("error", payload)
        details = error.get("details") if isinstance(error, dict) else None
        return [item for item in details or [] if isinstance(item, dict)]

    @staticmethod
    def _violations(exc: errors.APIError) -> list[dict[str, Any]]:
        return [
            violation
            for item in ApiErrors._details(exc)
            if item.get("@type", "").endswith("google.rpc.QuotaFailure")
            for violation in item.get("violations", [])
            if isinstance(violation, dict)
        ]
