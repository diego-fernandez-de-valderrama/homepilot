from enum import StrEnum


class WebStatus(StrEnum):
    NOT_NEEDED = "not_needed"
    SKIPPED = "skipped"
    OK = "ok"
    FAILED = "failed"
