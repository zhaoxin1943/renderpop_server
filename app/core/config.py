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
    redis_prefix: str = "renderpop_server_"
    session_secret: str = Field(default="change-me-to-a-long-random-string", min_length=8)

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/api/v1/auth/google/callback"

    # Dodo Payments: test_mode uses sandbox products; live_mode uses live products.
    dodo_api_key: str = ""
    dodo_webhook_key: str = ""
    dodo_environment: str = "test_mode"  # test_mode | live_mode
    dodo_return_url: str = "http://localhost:3000/billing/success"
    # Public base for provider webhooks (e.g. https://api.renderpop.app)
    public_api_base_url: str = "http://localhost:8000"

    runninghub_api_key: str = ""
    runninghub_base_url: str = "https://www.runninghub.ai"

    # Pollo AI video (text/image → video)
    pollo_api_key: str = ""
    pollo_base_url: str = "https://pollo.ai/api/platform"
    # Base64 secret from https://api.pollo.ai/webhook (optional; poll works without it)
    pollo_webhook_secret: str = ""

    aws_region: str = "us-east-2"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = "renderpop-assets"
    s3_asset_prefix: str = "media"

    # Dev-only: X-Dev-User-Id header accepted when environment=development
    allow_dev_auth: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def product_environment(self) -> str:
        """Map Dodo mode to products.environment column."""
        from app.models.enums import ProductEnvironment

        if self.dodo_environment == "live_mode":
            return ProductEnvironment.LIVE.value
        return ProductEnvironment.SANDBOX.value


@lru_cache
def get_settings() -> Settings:
    return Settings()
