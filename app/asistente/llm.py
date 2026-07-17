"""Abstracción del proveedor de LLM.

Dos caminos con proveedores primarios distintos, y el motivo es una limitación real del modelo:

- **Texto** (`completar`, `completar_stream`): Groq primario, OpenAI de respaldo. El grafo
  decide CUÁNDO cambiar (tras agotar reintentos); acá solo se resuelve el modelo y se llama.
- **Visión** (`extraer_de_imagen`): OpenAI único. `groq_model` es text-only y no puede ver
  una imagen, así que no hay respaldo posible.

Acá no vive lógica de decisión: solo se resuelve cada modelo desde la config y se expone una
llamada uniforme. Eso hace que el grafo sea agnóstico del SDK y que los tests reemplacen estas
funciones por stubs sin tocar red.

A pesar del nombre del paquete, este módulo es de facto la capa LLM de todo el proyecto, no
solo del asistente.
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


@lru_cache(maxsize=1)
def _openai_vision():
    """Cliente aparte para visión: mismo modelo, distinta tolerancia al tiempo.

    Es un cliente propio y no `_openai()` porque una llamada con una imagen adentro tarda
    segundos, no milisegundos, y quien la espera mantiene abierta una conexión de Postgres
    mientras tanto. Sin `request_timeout` explícito, una llamada colgada retiene esa conexión
    para siempre. Cambiarle el timeout a `_openai()` afectaría al asistente, que no lo necesita.
    """
    from langchain_openai import ChatOpenAI

    s = get_settings()
    return ChatOpenAI(
        model=s.openai_model,
        api_key=s.openai_api_key,
        temperature=0,
        request_timeout=s.ingesta_timeout_ms / 1000,
        max_retries=1,
    )


def completar(system: str, user: str, *, proveedor: str = GROQ) -> str:
    """Una llamada al LLM con system y user SEPARADOS (nunca concatenados — regla anti-injection).
    Devuelve el texto de la respuesta."""
    modelo = _openai() if proveedor == OPENAI else _groq()
    respuesta = modelo.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return respuesta.content if isinstance(respuesta.content, str) else str(respuesta.content)


def extraer_de_imagen(
    system: str,
    user: str,
    *,
    imagen_b64: str,
    mime: str,
    proveedor: str = OPENAI,
) -> str:
    """Una llamada multimodal: texto + imagen. Devuelve el texto crudo de la respuesta.

    Ojo con el default invertido: acá el primario es OPENAI, no GROQ. No es un capricho —
    `groq_model` (llama-3.3-70b-versatile) es TEXT-ONLY y no puede ver una imagen. Por eso
    esta función no tiene fallback: no hay un segundo proveedor multimodal configurado. Si
    OpenAI se cae, la llamada falla y el router responde un 502 genérico. Es honesto: mejor
    eso que fingir un camino de respaldo que no existe.

    El invariante anti-injection de `completar` se mantiene y de hecho se REFUERZA. El
    SystemMessage va intacto y separado; la imagen entra como un bloque de contenido dentro
    del turno HUMANO, que es exactamente lo que es: un dato aportado por el usuario, no una
    instrucción para el modelo. Nada se concatena.
    """
    if proveedor != OPENAI:
        raise ValueError(
            f"La visión requiere OPENAI: {proveedor!r} no es multimodal (groq_model es text-only)."
        )

    modelo = _openai_vision()
    respuesta = modelo.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(
                content=[
                    {"type": "text", "text": user},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{imagen_b64}"},
                    },
                ]
            ),
        ]
    )
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
