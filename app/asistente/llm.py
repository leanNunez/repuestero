"""Abstracción del proveedor de LLM. Groq primario, OpenAI de respaldo.

El grafo decide CUÁNDO cambiar de proveedor (tras agotar reintentos); acá solo se resuelve cada
modelo desde la config y se expone una función `completar` uniforme. Separar esto hace que el grafo
sea agnóstico del SDK y que los tests puedan reemplazar `completar` por un stub sin tocar red.
"""

from collections.abc import Iterator
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings

GROQ = "groq"
OPENAI = "openai"


@lru_cache(maxsize=1)
def _groq():
    from langchain_groq import ChatGroq

    s = get_settings()
    # temperature=0: para NL2SQL queremos SQL determinista, no creatividad.
    return ChatGroq(model=s.groq_model, api_key=s.groq_api_key, temperature=0)


@lru_cache(maxsize=1)
def _openai():
    from langchain_openai import ChatOpenAI

    s = get_settings()
    return ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0)


def completar(system: str, user: str, *, proveedor: str = GROQ) -> str:
    """Una llamada al LLM con system y user SEPARADOS (nunca concatenados — regla anti-injection).
    Devuelve el texto de la respuesta."""
    modelo = _openai() if proveedor == OPENAI else _groq()
    respuesta = modelo.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return respuesta.content if isinstance(respuesta.content, str) else str(respuesta.content)


def completar_stream(system: str, user: str, *, proveedor: str = GROQ) -> Iterator[str]:
    """Igual que `completar`, pero streamea la respuesta token por token (para el endpoint SSE).

    System y user van SEPARADOS (nunca concatenados — regla anti-injection). Emite el texto de cada
    chunk; los chunks vacíos (algunos modelos mandan uno al abrir/cerrar) se saltean."""
    modelo = _openai() if proveedor == OPENAI else _groq()
    for chunk in modelo.stream([SystemMessage(content=system), HumanMessage(content=user)]):
        texto = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
        if texto:
            yield texto
