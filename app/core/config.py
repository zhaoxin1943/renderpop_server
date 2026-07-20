from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    web_origin: str = "http://localhost:3000"
    api_prefix: str = "/api"

    # Async SQLAlchemy / SQLModel (aiomysql)
    database_url: str = (
        "mysql+aiomysql://renderpop:renderpop@127.0.0.1:3306/renderpop?charset=utf8mb4"
    )
    # Alembic and other sync tooling (pymysql)
    database_url_sync: str = (
        "mysql+pymysql://renderpop:renderpop@127.0.0.1:3306/renderpop?charset=utf8mb4"
    )

    redis_url: str = "redis://127.0.0.1:6379/0"
    # Shared Redis instance: all keys from this service MUST use this prefix.
    # Used as Dramatiq RedisBroker.namespace and app.core.redis_keys helper.
    redis_prefix: str = "renderpop_server_"
    session_secret: str = Field(default="change-me-to-a-long-random-string", min_length=8)

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/api/v1/auth/google/callback"

    dodo_api_key: str = ""
    dodo_webhook_key: str = ""
    runninghub_api_key: str = ""

    aws_region: str = "us-east-2"
    s3_bucket_name: str = "renderpop-assets"
    s3_asset_prefix: str = "media"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
