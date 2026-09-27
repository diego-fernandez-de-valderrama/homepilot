import re

MAX_EVIDENCE = 500
MAX_VALUE = 200
MIN_EVIDENCE = 3

_SPACES = re.compile(r"\s+")
_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "´": "'", "`": "'"})


def normalize(text: str) -> str:
    """Typographic quotes made plain, whitespace collapsed, casefolded."""
    return _SPACES.sub(" ", text.translate(_QUOTES)).strip().casefold()


def unquote(evidence: str) -> str:
    """The quote as the model passed it, without surrounding quote marks (case kept)."""
    return _SPACES.sub(" ", evidence.translate(_QUOTES)).strip().strip("\"'").strip()


def clean(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(v.strip()[:MAX_VALUE] for v in values or [] if v.strip()))
