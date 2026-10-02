import re
from urllib.parse import urlencode

from core.acciones import abrir_url_segura


def interpretar_mensaje(texto: str) -> tuple[str, str] | None:
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:;-]*)?"
        r"(?:env[ií]a(?:r|me|le)?|m[aá]nda(?:r|le|me)?)\s+a\s+"
        r"(.+?)\s+(?:un\s+)?mensaje"
        r"(?:\s+(?:que\s+diga|diciendo|de|con\s+el\s+texto))?"
        r"\s*[:,-]?\s*[\"“']?(.+?)[\"”']?\s*[.!?]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    destinatario = coincidencia.group(1).strip(" \t\"“”'")
    mensaje = coincidencia.group(2).strip(" \t\"“”'")
    if not destinatario or len(destinatario) > 80 or not mensaje:
        return None
    return destinatario, mensaje


def preparar_mensaje(destinatario: str, mensaje: str) -> str:
    destinatario = destinatario.strip()
    mensaje = mensaje.strip()
    if not destinatario or len(destinatario) > 80:
        raise ValueError("Indica un contacto de WhatsApp válido.")
    if not mensaje or len(mensaje) > 1000:
        raise ValueError("El mensaje debe tener entre 1 y 1000 caracteres.")

    url = "https://wa.me/?" + urlencode({"text": mensaje})
    abrir_url_segura(url)
    return (
        f"Abrí WhatsApp con el mensaje preparado para «{destinatario}». "
        "Elige manualmente ese contacto en la pantalla de WhatsApp, confirma "
        "que sea la persona correcta y pulsa Enviar. Jarvis no envió el mensaje."
    )
