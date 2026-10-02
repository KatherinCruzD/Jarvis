import re
import urllib.parse
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from core.acciones import abrir_url_segura


def abrir_cancion(consulta: str) -> str:
    consulta = consulta.strip()
    if not consulta or len(consulta) > 180:
        raise ValueError("Indica una canción con un nombre de hasta 180 caracteres.")

    opciones = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": True,
    }
    try:
        with YoutubeDL(opciones) as extractor:
            resultado = extractor.extract_info(
                f"ytsearch1:{consulta}", download=False
            )
    except DownloadError as error:
        raise RuntimeError(
            "No pude buscar esa canción en YouTube. Comprueba tu conexión a "
            "Internet y vuelve a intentarlo."
        ) from error

    entradas = resultado.get("entries") if resultado else None
    video = next((entrada for entrada in entradas or () if entrada), None)
    identificador = video.get("id") if video else None
    if not isinstance(identificador, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{11}", identificador
    ):
        raise RuntimeError(
            f"No encontré un video reproducible para {consulta!r} en YouTube."
        )

    url = "https://www.youtube.com/watch?" + urllib.parse.urlencode(
        {"v": identificador, "autoplay": "1"}
    )
    abrir_url_segura(url)
    titulo = video.get("title") or consulta
    return (
        f"Abrí «{titulo}» en YouTube. La reproducción es gratis; si el navegador "
        "bloquea el audio automático, pulsa Reproducir."
    )
