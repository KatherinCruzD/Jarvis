import re
import unicodedata

from core.pantalla import captura, ocr, vision

EXCLUIR = re.compile(
    r"captura de pantalla|pantallazo|brillo|volumen|apaga|reinicia|cierra|"
    r"pantalla completa de|protector de pantalla"
)
REFERENCIA = re.compile(
    r"\b(pantalla|ventana)\b|lo que (veo|ves|estoy viendo|estoy leyendo)|esto que (veo|ves)"
)
INTENCION = re.compile(
    r"\b(mira|mirar|ve|ver|revisa|revisar|lee|leer|explica|explicame|analiza|resume|"
    r"traduce|ayudame|dime|que significa|que dice|que error|que hay|que ves|no entiendo)\b"
)


def _simple(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def interpretar(texto: str):
    """Devuelve 'pantalla', 'ventana' o None si la frase no pide mirar la pantalla."""
    t = _simple(texto)
    if EXCLUIR.search(t) or not REFERENCIA.search(t) or not INTENCION.search(t):
        return None
    if re.search(r"toda la pantalla|pantalla completa", t):
        return "pantalla"
    if re.search(r"\bventana\b|este (error|parrafo|texto|codigo)", t):
        return "ventana"
    return "pantalla"


def manejar(texto: str):
    modo = interpretar(texto)
    if modo is None:
        return None

    try:
        imagen, donde = captura.capturar(modo)
    except Exception as error:
        return f"No pude capturar la pantalla: {error}"

    pregunta = f"{texto.strip()}\n(La captura muestra {donde}.)"
    en_la_nube = vision.proveedor_de_vision() == "gemini"
    try:
        # Con el modelo local, primero se lee el texto con OCR: es más rápido y más exacto.
        leido = "" if en_la_nube else ocr.leer_texto(imagen)
        if len(leido) >= ocr.MINIMO_CARACTERES:
            respuesta = vision.analizar_texto(leido, pregunta)
        else:
            respuesta = vision.analizar(imagen, pregunta)
    except Exception as error:
        return f"No pude analizar la pantalla: {error}"

    if en_la_nube:
        respuesta += " (Imagen analizada con Gemini, en la nube.)"
    return respuesta