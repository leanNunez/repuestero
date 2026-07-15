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

    # Asistente NL2SQL. El SQL del LLM corre con estas credenciales (rol app_readonly, solo SELECT).
    database_readonly_url: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_model: str = "gpt-4o-mini"
    #: Techo de filas y tiempo para el SQL del asistente (segunda reja además del rol read-only).
    asistente_max_filas: int = 200
    asistente_timeout_ms: int = 5000

    #: CORS. En prod NUNCA "*": lista separada por comas de orígenes permitidos.
    allowed_origins: str = "*"

    env: str = "dev"

    @property
    def is_prod(self) -> bool:
        return self.env == "production"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
