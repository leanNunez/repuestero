"""Embeddings del catálogo: un puerto, dos backends. Infra cross-cutting (como db/security).

El default es LOCAL: modelo `paraphrase-multilingual-MiniLM-L12-v2` (384 dims) en ONNX sobre CPU,
sin API key, sin costo, offline. Multilingüe → entiende español de repuestos. Es lo que usa dev y
el futuro mostrador offline.

El backend REMOTO (`EMBEDDINGS_BACKEND=remote`) genera el MISMO vector vía la HF Inference API, sin
cargar el modelo (~615MB en RAM) en el proceso. Existe para deploys con poca RAM (ej. Render free
512MB): con `remote` el backend baja de ~734MB a ~118MB. Verificado que ambos backends dan vectores
IDÉNTICOS (coseno 1.0), así que los embeddings ya indexados con el local conviven sin reindexar.

Es un modelo SIMÉTRICO: consulta y documento se embeben igual, sin prefijos (a diferencia de la
familia e5, que exige `query:`/`passage:`). Por eso `embed_query` y `embed_passages` comparten
codificación — se mantienen como dos funciones por claridad de intención y estabilidad de la API.
"""

from functools import lru_cache

from app.core.config import get_settings

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384


# ------------------------------------------------------------------ backend local (fastembed) ---
@lru_cache(maxsize=1)
def _modelo_local():
    """Carga perezosa y única. Instanciar fastembed baja el modelo (~120MB) la 1ª vez y es caro
    (~615MB en RAM): se hace una sola vez por proceso, recién cuando algo realmente lo necesita.
    Con `EMBEDDINGS_BACKEND=remote` esto NUNCA se llama → el modelo no se carga (ése es todo el punto)."""
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODELO)


def _embed_local(textos: list[str]) -> list[list[float]]:
    return [vec.tolist() for vec in _modelo_local().embed(textos)]


# ------------------------------------------------------------ backend remoto (HF Inference API) ---
@lru_cache(maxsize=1)
def _cliente_remoto():
    """Cliente único de la HF Inference API. `huggingface_hub` rutea el provider solo."""
    from huggingface_hub import InferenceClient

    token = get_settings().hf_token
    if not token:
        raise RuntimeError(
            "EMBEDDINGS_BACKEND=remote requiere HF_TOKEN en el entorno "
            "(token de HF con permiso 'Make calls to Inference Providers')."
        )
    return InferenceClient(token=token)


def _embed_remoto(textos: list[str]) -> list[list[float]]:
    import numpy as np

    cliente = _cliente_remoto()
    vectores: list[list[float]] = []
    for texto in textos:
        vec = np.asarray(cliente.feature_extraction(texto, model=MODELO), dtype=float)
        if vec.ndim == 2:  # algunos modelos devuelven token-level → mean pooling a (DIM,)
            vec = vec.mean(axis=0)
        vectores.append(vec.tolist())
    return vectores


# -------------------------------------------------------------------------------- puerto público ---
def _embed(textos: list[str]) -> list[list[float]]:
    """Despacha al backend configurado. La selección se lee en cada llamada (barato), pero el
    modelo/cliente quedan cacheados por su propio `lru_cache`."""
    if get_settings().embeddings_backend == "remote":
        return _embed_remoto(textos)
    return _embed_local(textos)


def embed_passages(textos: list[str]) -> list[list[float]]:
    """Embebe DOCUMENTOS para indexar. Batch: una llamada, N vectores."""
    if not textos:
        return []
    return _embed(textos)


def embed_query(texto: str) -> list[float]:
    """Embebe una CONSULTA de búsqueda."""
    return _embed([texto])[0]
