from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "SigDoc"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str

    # Auth
    secret_key: str
    admin_email: str = "admin@sigdoc.local"
    admin_password: str = "admin123"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_external_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
