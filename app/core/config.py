from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    migrations_database_url: str = ""

    supabase_url: str = ""
    supabase_jwks_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
