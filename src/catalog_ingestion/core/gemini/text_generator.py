from typing import Protocol

from google.genai import types


class TextGenerator(Protocol):
    """What the enricher and the url_context fetcher need from a Gemini client."""

    @property
    def model(self) -> str: ...

    def generate(self, contents: str, config: types.GenerateContentConfig) -> types.GenerateContentResponse: ...
