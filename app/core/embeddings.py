"""Embeddings locales con fastembed. Infra cross-cutting (como db/security).

Modelo `paraphrase-multilingual-MiniLM-L12-v2` (384 dims): corre en ONNX sobre CPU, sin API key,
sin costo y offline. Multilingüe → entiende español de repuestos. La búsqueda del catálogo y, más
adelante, el asistente conversacional se apoyan en este módulo.

Es un modelo SIMÉTRICO: consulta y documento se embeben igual, sin prefijos (a diferencia de la
familia e5, que exige `query:`/`passage:`). Por eso `embed_query` y `embed_passages` comparten
codificación — se mantienen como dos funciones por claridad de intención y estabilidad de la API.
"""

from functools import lru_cache

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384


@lru_cache(maxsize=1)
def _modelo():
    """Carga perezosa y única. Instanciar fastembed baja el modelo (~120MB) la 1ª vez y es caro:
    se hace una sola vez por proceso, recién cuando algo realmente necesita embeber."""
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODELO)


def embed_passages(textos: list[str]) -> list[list[float]]:
    """Embebe DOCUMENTOS para indexar. Batch: una llamada, N vectores."""
    if not textos:
        return []
    return [vec.tolist() for vec in _modelo().embed(textos)]


def embed_query(texto: str) -> list[float]:
    """Embebe una CONSULTA de búsqueda."""
    return next(iter(_modelo().embed([texto]))).tolist()
