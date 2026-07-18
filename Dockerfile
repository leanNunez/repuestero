# Backend de Repuestero. Deploy con EMBEDDINGS_BACKEND=remote: los embeddings los genera la HF
# Inference API, así el modelo (~615MB en RAM) NO se carga en el proceso y la imagen tampoco lo
# baquea. El backend baja de ~734MB a ~140MB de RSS → entra en hosts de 512MB. Ver docs/deploy.md.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# uv: compila bytecode y copia (no symlinks) → venv autocontenida en la imagen.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# libgomp1: lo necesita onnxruntime SÓLO si se usa el backend local de embeddings. Con el remoto no
# se carga; se deja instalado para que la misma imagen pueda correr también en modo local.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 1) Deps primero (capa cacheable): sólo lockfile, sin el proyecto. --no-dev = sin ruff/pytest.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) El código + instalación del proyecto.
COPY . .
RUN uv sync --frozen --no-dev

# El host inyecta $PORT. Corre las migraciones (idempotente) y levanta el server.
CMD uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
