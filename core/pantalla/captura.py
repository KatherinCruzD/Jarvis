import ctypes
import io
import os

import mss
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

ANCHO_MAXIMO = int(os.getenv("JARVIS_VISION_ANCHO", "1400"))
IGNORAR = {"program manager", "windows input experience", "microsoft text input application"}


def _activar_dpi() -> None:
    # Con zoom de Windows (125 %, 150 %) las coordenadas y los píxeles deben coincidir.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


_activar_dpi()


def _oculta_por_windows(manejador) -> bool:
    try:
        oculta = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            manejador, 14, ctypes.byref(oculta), ctypes.sizeof(oculta)
        )
        return bool(oculta.value)
    except Exception:
        return False


def ventana_objetivo():
    """La ventana visible más al frente que no sea el propio HUD de Jarvis."""
    try:
        import win32gui
    except ImportError:
        return None, None

    encontradas = []

    def revisar(manejador, _):
        if encontradas:
            return True
        if not win32gui.IsWindowVisible(manejador) or win32gui.IsIconic(manejador):
            return True
        titulo = win32gui.GetWindowText(manejador).strip()
        bajo = titulo.lower()
        if not titulo or bajo in IGNORAR or _oculta_por_windows(manejador):
            return True
        if bajo.startswith("jarvis") and "visual studio code" not in bajo:
            return True
        izquierda, arriba, derecha, abajo = win32gui.GetWindowRect(manejador)
        if derecha - izquierda < 200 or abajo - arriba < 150:
            return True
        encontradas.append((titulo, (izquierda, arriba, derecha, abajo)))
        return True

    try:
        win32gui.EnumWindows(revisar, None)
    except Exception:
        return None, None
    return encontradas[0] if encontradas else (None, None)


def _region_de_ventana(monitor: dict):
    titulo, rect = ventana_objetivo()
    if not rect:
        return None, None
    izquierda = max(rect[0], monitor["left"])
    arriba = max(rect[1], monitor["top"])
    derecha = min(rect[2], monitor["left"] + monitor["width"])
    abajo = min(rect[3], monitor["top"] + monitor["height"])
    if derecha - izquierda < 100 or abajo - arriba < 100:
        return None, None
    region = {
        "left": izquierda,
        "top": arriba,
        "width": derecha - izquierda,
        "height": abajo - arriba,
    }
    return region, titulo


def capturar(modo: str = "pantalla") -> tuple[bytes, str]:
    """Toma una captura y devuelve (imagen PNG en memoria, descripción de lo capturado)."""
    with mss.mss() as pantalla:
        monitor = dict(pantalla.monitors[1])
        descripcion = "toda la pantalla"
        if modo == "ventana":
            region, titulo = _region_de_ventana(monitor)
            if region:
                monitor = region
                descripcion = f"la ventana «{titulo}»"
        captura = pantalla.grab(monitor)
        imagen = Image.frombytes("RGB", captura.size, captura.bgra, "raw", "BGRX")

    imagen.thumbnail((ANCHO_MAXIMO, ANCHO_MAXIMO))
    memoria = io.BytesIO()
    imagen.save(memoria, format="PNG")
    return memoria.getvalue(), descripcion