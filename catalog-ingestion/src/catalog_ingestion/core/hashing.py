import hashlib
import json
from typing import Any


class Hashing:
    """Stable content hashes used to decide which pipeline stages must re-run."""

    @staticmethod
    def canonical_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def sha256_json(value: Any) -> str:
        return Hashing.sha256_text(Hashing.canonical_json(value))
