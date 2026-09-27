from pydantic_settings import SettingsConfigDict


class EnvConfig:
    """The pydantic-settings configuration shared by every settings class: one env prefix per concern,
    read from the environment and an optional `.env` in the current working directory."""

    ENV_FILE = ".env"

    @staticmethod
    def for_prefix(prefix: str) -> SettingsConfigDict:
        return SettingsConfigDict(
            env_prefix=prefix,
            env_file=EnvConfig.ENV_FILE,
            env_file_encoding="utf-8",
            extra="ignore",
        )
