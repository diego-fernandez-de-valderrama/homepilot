from pydantic import Field
from pydantic_settings import BaseSettings

from catalog_ingestion.core.settings._env_config import EnvConfig


class WebSettings(BaseSettings):
    model_config = EnvConfig.for_prefix("WEB_")

    enabled: bool = True
    timeout_seconds: float = Field(default=15.0, gt=0)
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    max_text_chars: int = Field(default=20_000, gt=0)
