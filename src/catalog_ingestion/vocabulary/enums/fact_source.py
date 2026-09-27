from enum import StrEnum


class FactSource(StrEnum):
    """Where the evidence for a fact was found."""

    CATALOG = "catalog"  # the original JSON from products.zip
    WEB = "web"  # the product page referenced by the dataset URL
    LLM = "llm"  # derived by the LLM without a verbatim quote (descriptive fields only)
