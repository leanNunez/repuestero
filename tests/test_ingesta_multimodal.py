"""El camino multimodal y la validación de la imagen (slice 3).

Sin red y sin DB: se monkeypatchea el cliente de visión por un fake que CAPTURA los mensajes.
Eso permite verificar la propiedad que más importa —que el system prompt no se mezcle nunca
con el contenido que aporta el usuario— sin gastar un token.
"""

import base64

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.asistente import llm
from app.ingesta_visual import imagen

# Imágenes mínimas pero REALES: los magic bytes son lo que se está verificando.
_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 12
_WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 8

_JPEG_B64 = base64.b64encode(_JPEG).decode()


class _ModeloFake:
    """Captura los mensajes que recibiría el modelo, sin llamar a nadie."""

    def __init__(self, respuesta: str = '{"renglones": []}') -> None:
        self.respuesta = respuesta
        self.mensajes = None
        self.llamadas = 0

    def invoke(self, mensajes):
        self.mensajes = mensajes
        self.llamadas += 1
        return type("R", (), {"content": self.respuesta})()


# --------------------------------------------------------------------------- el invariante

def test_system_y_user_van_separados_y_la_imagen_es_del_turno_humano(monkeypatch):
    """EL test de seguridad del camino multimodal.

    Verifica dos cosas que juntas cierran la puerta principal del prompt injection por imagen:
    1. El system prompt viaja en su PROPIO mensaje, nunca concatenado con el input del usuario.
    2. La imagen entra como un bloque dentro del turno HUMANO — que es lo que es: un dato
       aportado, no una instrucción. Si entrara en el system, cualquier texto impreso en el
       papel tendría el mismo rango que nuestras reglas.
    """
    fake = _ModeloFake()
    monkeypatch.setattr(llm, "_openai_vision", lambda: fake)

    llm.extraer_de_imagen(
        "SOS UN EXTRACTOR", "Extraé los renglones", imagen_b64=_JPEG_B64, mime="image/jpeg"
    )

    system, human = fake.mensajes
    assert isinstance(system, SystemMessage)
    assert isinstance(human, HumanMessage)
    assert system.content == "SOS UN EXTRACTOR"

    # El system NO aparece adentro del turno humano.
    assert "SOS UN EXTRACTOR" not in str(human.content)

    # El turno humano lleva dos bloques: el texto y la imagen.
    tipos = [b["type"] for b in human.content]
    assert tipos == ["text", "image_url"]
    assert human.content[0]["text"] == "Extraé los renglones"
    assert human.content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_visión_con_groq_falla_ruidoso_y_sin_red(monkeypatch):
    """groq_model es text-only. Si alguien le pasa GROQ, tiene que explotar ACÁ y fuerte,
    no fallar con un 400 críptico del proveedor a mitad de camino."""
    llamado = False

    def _no_deberia_llamarse():
        nonlocal llamado
        llamado = True

    monkeypatch.setattr(llm, "_openai_vision", _no_deberia_llamarse)

    with pytest.raises(ValueError, match="multimodal"):
        llm.extraer_de_imagen(
            "sys", "user", imagen_b64=_JPEG_B64, mime="image/jpeg", proveedor=llm.GROQ
        )

    assert not llamado


def test_extraer_devuelve_el_texto_crudo(monkeypatch):
    """La capa LLM transporta strings. El parseo a Pydantic vive en el extractor."""
    fake = _ModeloFake(respuesta='{"renglones": [{"codigo": "X"}]}')
    monkeypatch.setattr(llm, "_openai_vision", lambda: fake)

    out = llm.extraer_de_imagen("s", "u", imagen_b64=_JPEG_B64, mime="image/jpeg")

    assert out == '{"renglones": [{"codigo": "X"}]}'


# --------------------------------------------------------------------------- validación

@pytest.mark.parametrize(
    ("datos", "mime"),
    [(_JPEG, "image/jpeg"), (_PNG, "image/png"), (_WEBP, "image/webp")],
)
def test_decodifica_los_tres_formatos_aceptados(datos, mime):
    b64 = base64.b64encode(datos).decode()
    assert imagen.decodificar(b64, mime) == datos


def test_mime_mentiroso_se_rechaza():
    """El caso que importa: el mime lo elige quien manda el request, así que no es evidencia.
    Lo que decide es la firma de los bytes."""
    b64 = base64.b64encode(_JPEG).decode()

    with pytest.raises(imagen.ImagenInvalida, match="dice ser"):
        imagen.decodificar(b64, "image/png")


def test_archivo_que_no_es_imagen_se_rechaza():
    """Un ejecutable renombrado a .jpg no llega al modelo."""
    b64 = base64.b64encode(b"MZ\x90\x00\x03PAYLOAD").decode()

    with pytest.raises(imagen.ImagenInvalida, match="no es una imagen"):
        imagen.decodificar(b64, "image/jpeg")


def test_base64_basura_se_rechaza():
    with pytest.raises(imagen.ImagenInvalida, match="base64"):
        imagen.decodificar("no-soy-base64!!!", "image/jpeg")


def test_formato_no_aceptado_se_rechaza_antes_de_decodificar():
    """Un GIF (o un PDF, o un SVG con script) ni siquiera se decodifica."""
    with pytest.raises(imagen.ImagenInvalida, match="Formato no aceptado"):
        imagen.decodificar(base64.b64encode(b"GIF89a").decode(), "image/gif")


def test_imagen_vacia_se_rechaza():
    with pytest.raises(imagen.ImagenInvalida, match="vacía"):
        imagen.decodificar("", "image/jpeg")


# --------------------------------------------------------------------------- hash

def test_hash_es_de_los_bytes_no_del_string_base64():
    """El mismo archivo puede llegar con distinto whitespace en el base64. Si el hash fuera
    del string, el candado de idempotencia dejaría pasar el mismo remito dos veces."""
    limpio = base64.b64encode(_JPEG).decode()
    con_saltos = "\n".join([limpio[i : i + 20] for i in range(0, len(limpio), 20)])

    assert con_saltos != limpio
    assert imagen.hash_imagen(base64.b64decode(limpio)) == imagen.hash_imagen(
        base64.b64decode(con_saltos)
    )


def test_hash_distinto_para_imagenes_distintas():
    assert imagen.hash_imagen(_JPEG) != imagen.hash_imagen(_PNG)


def test_hash_tiene_forma_de_sha256():
    h = imagen.hash_imagen(_JPEG)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# --------------------------------------------------------------------------- techo de tamaño

def test_max_chars_base64_deja_pasar_el_limite_y_frena_lo_de_arriba():
    """El techo se calcula sobre el STRING base64 porque es lo que llega por la red: hay que
    poder rechazarlo ANTES de decodificarlo. Decodificar para después rechazar ES el DoS."""
    techo = imagen.max_chars_base64(8)

    justo = base64.b64encode(b"\xff" * (8 * 1024 * 1024)).decode()
    assert len(justo) <= techo

    pasado = base64.b64encode(b"\xff" * (9 * 1024 * 1024)).decode()
    assert len(pasado) > techo
