"""Validación y hash de la imagen del remito. Funciones puras: sin DB, sin LLM, sin red.

El orden importa y es la defensa. La validación de TAMAÑO ocurre en el boundary de Pydantic,
sobre el string base64, ANTES de que nada acá lo decodifique: decodificar 500 MB de base64
para recién después rechazarlos ES el ataque, no la protección contra él.
"""

import base64
import hashlib

#: Los únicos formatos que aceptamos. Son los que produce la cámara de un celular y los que
#: entiende la API de visión.
MIMES_ACEPTADOS = ("image/jpeg", "image/png", "image/webp")

#: Firmas reales de cada formato (los primeros bytes del archivo).
_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


class ImagenInvalida(ValueError):
    """La imagen no se puede procesar. El router la traduce a un 422."""


def max_chars_base64(max_mb: int) -> int:
    """Cuántos caracteres de base64 ocupa, como máximo, una imagen de `max_mb`.

    Este número es el `max_length` del campo Pydantic: el techo tiene que estar del lado del
    string, que es lo que efectivamente llega por la red.

    Es `4 * ceil(bytes/3)` y NO `ceil(bytes*4/3)`: base64 emite bloques de 4 caracteres y
    rellena el último con padding. Para 8 MB la diferencia es de un solo carácter — el
    justo que haría rebotar un archivo de exactamente 8 MB.
    """
    bytes_max = max_mb * 1024 * 1024
    return 4 * -(-bytes_max // 3)  # techo entero, sin float


def _formato_real(datos: bytes) -> str | None:
    """El formato según los BYTES, no según lo que el cliente dice que mandó."""
    for mime, firmas in _MAGIC.items():
        if any(datos.startswith(f) for f in firmas):
            return mime
    # WEBP es RIFF....WEBP: el tamaño va en el medio, así que no sirve un startswith solo.
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


def decodificar(imagen_b64: str, mime: str) -> bytes:
    """Decodifica y verifica que la imagen SEA lo que dice ser.

    El mime declarado no es evidencia: lo elige quien manda el request. Lo que decide es la
    firma de los bytes. Si no coinciden, el archivo se rechaza — no se "corrige" el mime,
    porque un archivo que miente sobre su tipo no es un archivo que queramos procesar.
    """
    if mime not in MIMES_ACEPTADOS:
        raise ImagenInvalida(f"Formato no aceptado: {mime}")

    try:
        datos = base64.b64decode(imagen_b64, validate=True)
    except Exception as exc:
        raise ImagenInvalida("La imagen no es base64 válido.") from exc

    if not datos:
        raise ImagenInvalida("La imagen está vacía.")

    real = _formato_real(datos)
    if real is None:
        raise ImagenInvalida("El archivo no es una imagen JPEG, PNG ni WEBP.")
    if real != mime:
        raise ImagenInvalida(f"El archivo dice ser {mime} pero es {real}.")

    return datos


def hash_imagen(datos: bytes) -> str:
    """sha256 de los BYTES de la imagen.

    De los bytes y no del string base64 a propósito: el mismo archivo puede llegar con
    distinto padding o whitespace y daría otro hash, y entonces el candado de idempotencia
    dejaría pasar el mismo remito dos veces.
    """
    return hashlib.sha256(datos).hexdigest()
