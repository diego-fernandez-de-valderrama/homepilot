from enum import StrEnum
from typing import Literal

from catalog_ingestion.vocabulary import CategoryVocabulary

# Types of the LLM output schema: Gemini may only answer with these values.
CategoryKey = StrEnum("CategoryKey", {key: key for key in CategoryVocabulary.KEYS})
ClaimDimension = Literal["ecosystem", "voice_assistant", "protocol", "mobile_os"]
ClaimSource = Literal["catalog", "web"]
