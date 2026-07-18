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

    # Embeddings del catálogo. "local" = fastembed en el proceso (offline, sin costo, default,
    # lo que usa dev y el futuro mostrador offline). "remote" = HF Inference API (MISMO modelo y
    # MISMO vector) sin cargar el modelo de ~615MB en RAM → para deploys con poca RAM (Render free
    # 512MB). Ver app/core/embeddings.py y docs/deploy.md.
    embeddings_backend: str = "local"
    #: Token de la HF Inference API (permiso "Make calls to Inference Providers"). Solo lo usa el
    #: backend "remote".
    hf_token: str = ""
    #: Techo de filas y tiempo para el SQL del asistente (segunda reja además del rol read-only).
    asistente_max_filas: int = 200
    asistente_timeout_ms: int = 5000

    # Ingesta visual (remito por foto). Usa openai_model: es multimodal, groq_model NO.
    #: Techo del archivo. Una foto de celular moderno ronda los 3-5 MB; 8 deja margen sin
    #: que un upload gigante llegue nunca a decodificarse.
    ingesta_max_imagen_mb: int = 8
    #: Techo de renglones por remito. Un "remito" de 5000 renglones no puede inflar la DB
    #: ni la factura de tokens.
    ingesta_max_renglones: int = 50
    #: Debajo de esto, el renglón se marca para atención humana. Es un HINT de UI, nunca un
    #: gate: la confianza que un LLM se auto-reporta está mal calibrada. El gate es el humano.
    ingesta_umbral_confianza: float = 0.75
    #: Timeout de la llamada de visión. Sin esto, una llamada colgada retiene una conexión
    #: de Postgres indefinidamente (ver la nota en ingesta_visual/router.py).
    ingesta_timeout_ms: int = 30000

    #: CORS. En prod NUNCA "*": lista separada por comas de orígenes permitidos.
    allowed_origins: str = "*"

    env: str = "dev"

    @property
    def is_prod(self) -> bool:
        # Acepta "prod" y "production": Render/HF suelen setear "prod" y no queremos que un
        # typo deje Swagger abierto en producción. Normaliza mayúsculas por las dudas.
        return self.env.strip().lower() in ("production", "prod")

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
