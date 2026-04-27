from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "SigDoc"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]
    bulk_generation_limit: int = 10

    # Rate limits
    rate_limit_login: str = "5/minute"
    rate_limit_refresh: str = "10/minute"
    rate_limit_generate: str = "20/minute"
    rate_limit_generate_bulk: str = "5/minute"
    rate_limit_signup: str = "3/hour"

    # Database
    database_url: str

    # Auth
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Email
    email_backend: str = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@sigdoc.local"
    smtp_tls: bool = True
    frontend_url: str = "http://localhost:5173"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_external_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False

    # Gotenberg (PDF conversion service)
    gotenberg_url: str = "http://gotenberg:3000"
    gotenberg_timeout: int = 60  # seconds

    # Dev recovery endpoint (NEVER enable in production)
    enable_dev_reset: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
