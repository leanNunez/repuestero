"""Tests del selector de backend de embeddings (local vs remoto).

No tocan Postgres ni la red: mockean los backends para verificar el DESPACHO y, sobre todo, que
`remote` NO instancia fastembed (que es el punto de todo — la RAM del deploy). El backend `local`
real ya lo ejercita test_busqueda.py contra fastembed de verdad.
"""

import numpy as np
import pytest

from app.core import embeddings
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _limpiar_caches():
    """Cada test parte con settings, modelo y cliente sin cachear."""
    get_settings.cache_clear()
    embeddings._modelo_local.cache_clear()
    embeddings._cliente_remoto.cache_clear()
    yield
    get_settings.cache_clear()
    embeddings._modelo_local.cache_clear()
    embeddings._cliente_remoto.cache_clear()


def test_default_es_local(monkeypatch):
    monkeypatch.delenv("EMBEDDINGS_BACKEND", raising=False)
    get_settings.cache_clear()
    assert get_settings().embeddings_backend == "local"


def test_local_no_toca_la_api_remota(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "local")
    get_settings.cache_clear()

    monkeypatch.setattr(
        embeddings, "_cliente_remoto", lambda: pytest.fail("local no debe tocar la API remota")
    )
    monkeypatch.setattr(
        embeddings, "_embed_local", lambda textos: [[0.1] * embeddings.DIM for _ in textos]
    )

    assert len(embeddings.embed_query("filtro")) == embeddings.DIM


def test_remote_no_carga_fastembed(monkeypatch):
    """EL test que importa: con `remote`, el modelo local NUNCA se instancia (ahorro de RAM)."""
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "remote")
    get_settings.cache_clear()

    def _explota():
        raise AssertionError("remote NO debe cargar fastembed")

    monkeypatch.setattr(embeddings, "_modelo_local", _explota)

    class _FakeCliente:
        def feature_extraction(self, texto, model):
            return np.full(embeddings.DIM, 0.5)

    monkeypatch.setattr(embeddings, "_cliente_remoto", lambda: _FakeCliente())

    vec = embeddings.embed_query("filtro de aceite")
    assert len(vec) == embeddings.DIM
    assert vec[0] == pytest.approx(0.5)


def test_remote_mean_pooling_si_token_level(monkeypatch):
    """Si la API devuelve token-level (2D), se promedia a un solo vector (DIM,)."""
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "remote")
    get_settings.cache_clear()

    class _FakeCliente:
        def feature_extraction(self, texto, model):
            return np.array([[0.0] * embeddings.DIM, [1.0] * embeddings.DIM])

    monkeypatch.setattr(embeddings, "_cliente_remoto", lambda: _FakeCliente())

    vec = embeddings.embed_query("hola")
    assert len(vec) == embeddings.DIM
    assert vec[0] == pytest.approx(0.5)


def test_remote_batch_devuelve_n_vectores(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "remote")
    get_settings.cache_clear()

    class _FakeCliente:
        def feature_extraction(self, texto, model):
            return np.full(embeddings.DIM, 0.3)

    monkeypatch.setattr(embeddings, "_cliente_remoto", lambda: _FakeCliente())

    vecs = embeddings.embed_passages(["a", "b", "c"])
    assert len(vecs) == 3
    assert all(len(v) == embeddings.DIM for v in vecs)


def test_embed_passages_vacio_no_llama_al_backend(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "remote")
    get_settings.cache_clear()
    monkeypatch.setattr(
        embeddings, "_cliente_remoto", lambda: pytest.fail("no debe llamar al backend si no hay textos")
    )
    assert embeddings.embed_passages([]) == []


def test_remote_sin_token_falla_claro(monkeypatch):
    """Sin HF_TOKEN, el backend remoto falla con un mensaje accionable, no un error oscuro."""
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "remote")
    monkeypatch.setenv("HF_TOKEN", "")
    get_settings.cache_clear()
    embeddings._cliente_remoto.cache_clear()
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        embeddings.embed_query("x")
