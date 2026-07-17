# Backend de Repuestero para Render. La imagen trae el modelo fastembed YA baqueado, así el
# arranque no baja ~120MB en cada cold start del plan free.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# uv: compila bytecode y copia (no symlinks) → venv autocontenida en la imagen.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache

WORKDIR /app

# onnxruntime (lo usa fastembed) necesita libgomp1; la imagen slim no lo trae.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 1) Deps primero (capa cacheable): sólo lockfile, sin el proyecto. --no-dev = sin ruff/pytest.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) El código + instalación del proyecto.
COPY . .
RUN uv sync --frozen --no-dev

# 3) Bakear el modelo de embeddings en la imagen (descarga en build, nunca en runtime).
RUN uv run python -c "from app.core.embeddings import embed_query; embed_query('warmup')"

# Render inyecta $PORT. Corre las migraciones (idempotente) y levanta el server.
CMD uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
