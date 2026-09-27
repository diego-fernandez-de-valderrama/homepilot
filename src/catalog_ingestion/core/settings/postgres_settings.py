from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy import URL

from catalog_ingestion.core.settings._env_config import EnvConfig


class PostgresSettings(BaseSettings):
    model_config = EnvConfig.for_prefix("POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    db: str = "catalog"
    user: str = "catalog"
    password: SecretStr = SecretStr("catalog")

    @property
    def url(self) -> URL:
        """SQLAlchemy URL (psycopg 3 driver). Special characters in the password are escaped."""
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )
