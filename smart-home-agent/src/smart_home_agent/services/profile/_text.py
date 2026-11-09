from catalog_ingestion.core import TextNormalizer

MAX_EVIDENCE = 500
MAX_VALUE = 200
MIN_EVIDENCE = 3


def unquote(evidence: str) -> str:
    """The quote as the model passed it, without surrounding quote marks or backticks (case kept)."""
    return TextNormalizer.fold(evidence).strip().strip("\"'`").strip()


def clean(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(v.strip()[:MAX_VALUE] for v in values or [] if v.strip()))
