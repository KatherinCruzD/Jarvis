import io
import os

from PIL import Image

# Idiomas de OCR de Windows, del más cercano al tuyo al menos cercano.
IDIOMAS = ("es-MX", "es-ES", "es", "en-US")
MINIMO_CARACTERES = 80


def ocr_activo() -> bool:
    return os.getenv("JARVIS_OCR", "1").strip() != "0"


def leer(png: bytes) -> tuple[str, str]:
    """Lee el texto de una imagen con el OCR de Windows. Devuelve (texto, idioma usado)."""
    if not ocr_activo():
        return "", ""
    try:
        import winocr

        imagen = Image.open(io.BytesIO(png))
    except Exception:
        return "", ""

    for idioma in IDIOMAS:
        try:
            resultado = winocr.recognize_pil_sync(imagen, idioma)
        except AssertionError:
            continue  # ese idioma de OCR no está instalado en Windows
        except Exception:
            return "", ""
        return (resultado.get("text") or "").strip(), idioma
    return "", ""


def leer_texto(png: bytes) -> str:
    return leer(png)[0]