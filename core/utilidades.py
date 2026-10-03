import ast
import ctypes
import json
import operator
import os
import re
import secrets
import string
import subprocess
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import psutil
from PIL import ImageGrab

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

CARPETA_DATOS = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Jarvis"
ARCHIVO_DATOS = CARPETA_DATOS / "datos.json"

CARPETAS = {
    "documentos": "Documents",
    "descargas": "Downloads",
    "escritorio": "Desktop",
    "imagenes": "Pictures",
    "fotos": "Pictures",
    "musica": "Music",
    "videos": "Videos",
}


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


# ---------- Hora, fecha y sistema ----------

def hora_actual() -> str:
    ahora = datetime.now()
    hora12 = ahora.hour % 12 or 12
    if ahora.hour < 12:
        momento = "de la mañana"
    elif ahora.hour < 19:
        momento = "de la tarde"
    else:
        momento = "de la noche"
    verbo = "Es la" if hora12 == 1 else "Son las"
    return f"{verbo} {hora12}:{ahora.minute:02d} {momento}."


def fecha_actual() -> str:
    hoy = datetime.now()
    return (
        f"Hoy es {DIAS[hoy.weekday()]} {hoy.day} de "
        f"{MESES[hoy.month - 1]} de {hoy.year}."
    )


def info_sistema() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    disco = psutil.disk_usage(Path.home().anchor or "C:\\").percent
    partes = [
        f"CPU al {cpu:.0f} por ciento",
        f"memoria RAM al {ram:.0f} por ciento",
        f"disco al {disco:.0f} por ciento",
    ]
    bateria = psutil.sensors_battery()
    if bateria is not None:
        estado = "cargando" if bateria.power_plugged else "usando la batería"
        partes.append(f"batería al {bateria.percent:.0f} por ciento, {estado}")
    return ", ".join(partes) + "."


# ---------- Contraseñas y calculadora ----------

def generar_contrasena(longitud: int = 16) -> str:
    longitud = max(8, min(longitud, 64))
    alfabeto = string.ascii_letters + string.digits + "!@#$%&*?"
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


_OPERACIONES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}
_PALABRAS = [
    ("multiplicado por", "*"), ("dividido entre", "/"), ("dividido por", "/"),
    ("elevado a", "**"), ("más", "+"), ("menos", "-"), ("por", "*"), ("entre", "/"),
]


def _evaluar(nodo):
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return nodo.value
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERACIONES:
        izquierda = _evaluar(nodo.left)
        derecha = _evaluar(nodo.right)
        if isinstance(nodo.op, ast.Pow) and abs(derecha) > 100:
            raise ValueError("exponente demasiado grande")
        return _OPERACIONES[type(nodo.op)](izquierda, derecha)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _OPERACIONES:
        return _OPERACIONES[type(nodo.op)](_evaluar(nodo.operand))
    raise ValueError("operación no permitida")


def calcular(texto: str):
    expresion = texto.lower().replace(",", ".")
    for palabra, simbolo in _PALABRAS:
        expresion = expresion.replace(palabra, simbolo)
    expresion = re.sub(r"[^0-9+\-*/(). ]", "", expresion).strip()
    try:
        resultado = _evaluar(ast.parse(expresion, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(resultado, float) and resultado.is_integer():
        resultado = int(resultado)
    elif isinstance(resultado, float):
        resultado = round(resultado, 6)
    return f"El resultado es {resultado}."


# ---------- Volumen, música y capturas ----------

_VOLUMEN = {"silenciar": 0xAD, "bajar": 0xAE, "subir": 0xAF}
_MULTIMEDIA = {"pausa": 0xB3, "siguiente": 0xB0, "anterior": 0xB1}


def _pulsar(codigo: int, veces: int = 1) -> None:
    for _ in range(veces):
        ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codigo, 0, 2, 0)


def volumen(accion: str, pasos: int = 5) -> str:
    _pulsar(_VOLUMEN[accion], 1 if accion == "silenciar" else pasos)
    return {
        "subir": "Volumen más alto.",
        "bajar": "Volumen más bajo.",
        "silenciar": "Listo, cambié el silencio.",
    }[accion]


def brillo(accion: str) -> str:
    if os.name != "nt":
        return "El control de brillo solo está disponible en Windows."
    ajuste = 10 if accion == "subir" else -10
    comando = (
        "$monitores = Get-CimInstance -Namespace root/WMI "
        "-ClassName WmiMonitorBrightness; "
        "if (-not $monitores) { throw 'No se encontró un monitor con brillo ajustable.' }; "
        f"$ajuste = {ajuste}; "
        "foreach ($monitor in $monitores) { "
        "$nivel = [Math]::Max(0, [Math]::Min(100, "
        "[int]$monitor.CurrentBrightness + $ajuste)); "
        "$metodo = Get-CimInstance -Namespace root/WMI "
        "-ClassName WmiMonitorBrightnessMethods | "
        "Where-Object InstanceName -eq $monitor.InstanceName; "
        "if (-not $metodo) { throw 'No se encontró el control de brillo del monitor.' }; "
        "Invoke-CimMethod -InputObject $metodo -MethodName WmiSetBrightness "
        "-Arguments @{ Timeout = 0; Brightness = $nivel } | Out-Null }; "
        "'Brillo ajustado a ' + $nivel + '%.'"
    )
    try:
        resultado = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", comando],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return "No encontré PowerShell para cambiar el brillo."
    except subprocess.TimeoutExpired:
        return "El control de brillo tardó demasiado y se canceló."
    except OSError as error:
        return f"No pude iniciar el control de brillo: {error}"
    except subprocess.CalledProcessError as error:
        detalle = (error.stderr or "").strip()
        return f"No pude cambiar el brillo: {detalle or 'el monitor no admite este control.'}"
    return resultado.stdout.strip() or "Se actualizó el brillo del monitor."


def musica(accion: str) -> str:
    _pulsar(_MULTIMEDIA[accion])
    return {
        "pausa": "Listo, pausé o reanudé la música.",
        "siguiente": "Pasando a la siguiente canción.",
        "anterior": "Volviendo a la canción anterior.",
    }[accion]


def tomar_captura() -> str:
    carpeta = Path.home() / "Pictures" / "Capturas Jarvis"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"captura_{datetime.now():%Y%m%d_%H%M%S}.png"
    ImageGrab.grab().save(ruta)
    return "Listo, guardé la captura en Imágenes, carpeta Capturas Jarvis."


# ---------- Carpetas ----------

def abrir_carpeta(nombre: str) -> str:
    ruta = Path.home() / CARPETAS[nombre]
    if not ruta.exists():
        return f"No encontré la carpeta {nombre}."
    os.startfile(ruta)
    return f"Abriendo {nombre}."


# ---------- Notas y tareas ----------

def _cargar() -> dict:
    try:
        return json.loads(ARCHIVO_DATOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"notas": [], "tareas": []}


def _guardar(datos: dict) -> None:
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    ARCHIVO_DATOS.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def agregar_nota(texto: str) -> str:
    datos = _cargar()
    datos.setdefault("notas", []).append(texto)
    _guardar(datos)
    return "Listo, guardé la nota."


def listar_notas() -> str:
    notas = _cargar().get("notas", [])
    if not notas:
        return "No tienes notas guardadas."
    return "Tus notas: " + "; ".join(f"{i}, {n}" for i, n in enumerate(notas, 1)) + "."


def agregar_tarea(texto: str) -> str:
    datos = _cargar()
    datos.setdefault("tareas", []).append({"texto": texto, "hecha": False})
    _guardar(datos)
    return "Listo, agregué la tarea."


def listar_tareas() -> str:
    tareas = _cargar().get("tareas", [])
    pendientes = [
        f"{i}, {t['texto']}" for i, t in enumerate(tareas, 1) if not t["hecha"]
    ]
    if not pendientes:
        return "No tienes tareas pendientes."
    return "Tareas pendientes: " + "; ".join(pendientes) + "."


def completar_tarea(numero: int) -> str:
    datos = _cargar()
    tareas = datos.get("tareas", [])
    if not 1 <= numero <= len(tareas):
        return "No encontré esa tarea."
    tareas[numero - 1]["hecha"] = True
    _guardar(datos)
    return f"Listo, marqué como hecha la tarea {numero}."


# ---------- Apagar y reiniciar (con confirmación) ----------

_pendiente = {"accion": None, "hasta": 0.0}


def _pedir_confirmacion(accion: str) -> str:
    _pendiente["accion"] = accion
    _pendiente["hasta"] = time.time() + 30
    return f"¿Seguro que quieres {accion} el computador? Di «confirmo» en los próximos 30 segundos."


def _confirmar():
    accion = _pendiente["accion"]
    vigente = accion is not None and time.time() <= _pendiente["hasta"]
    _pendiente["accion"] = None
    if not vigente:
        return None
    bandera = "/s" if accion == "apagar" else "/r"
    subprocess.run(["shutdown", bandera, "/t", "30"], check=False)
    verbo = "apagará" if accion == "apagar" else "reiniciará"
    return (
        f"Entendido, el computador se {verbo} en 30 segundos. "
        "Di «cancela el apagado» para detenerlo."
    )


def cancelar_apagado() -> str:
    resultado = subprocess.run(["shutdown", "/a"], check=False, capture_output=True)
    if resultado.returncode == 0:
        return "Apagado cancelado."
    return "No había ningún apagado programado."


# ---------- Punto de entrada ----------

def manejar(texto: str):
    limpio = texto.strip(" ¿?¡!.,")
    t = limpio.lower()
    sin = _sin_tildes(t)

    if re.fullmatch(r"(?:sí,? )?confirmo(?: (?:el )?(?:apagado|reinicio))?", t):
        return _confirmar()
    if re.search(r"cancela(?:r)? (?:el )?(?:apagado|reinicio)", t):
        return cancelar_apagado()
    if re.search(r"\b(apaga|reinicia)\b.*\b(computador|computadora|pc|equipo)\b", t):
        return _pedir_confirmacion("apagar" if "apaga" in t else "reiniciar")

    if re.search(r"qué hora|dime la hora|la hora actual", t):
        return hora_actual()
    if re.search(r"qué (día|fecha)|fecha de hoy|día es hoy", t):
        return fecha_actual()
    if re.search(
        r"\bcpu\b|\bram\b|batería|información del sistema|estado del (pc|computador|sistema)",
        t,
    ):
        return info_sistema()

    if "contraseña" in t and re.search(r"genera|crea|dame|nueva", t):
        return f"Tu contraseña nueva es {generar_contrasena()}. Guárdala en un lugar seguro."
    if re.search(r"cuánto es|cuánto son|calcula", t):
        resultado = calcular(t)
        if resultado:
            return resultado

    if "captura de pantalla" in t or "pantallazo" in t:
        return tomar_captura()

    carpeta = re.search(
        r"abre(?: la carpeta de| la carpeta| mis| mi carpeta de)? "
        r"(documentos|descargas|escritorio|imagenes|fotos|musica|videos)\b",
        sin,
    )
    if carpeta:
        return abrir_carpeta(carpeta.group(1))

    if re.search(r"\b(música|canción|reproducción)\b", t):
        if re.search(r"pausa|pausar|reanuda|continúa", t):
            return musica("pausa")
        if re.search(r"siguiente|próxima|salta", t):
            return musica("siguiente")
        if re.search(r"anterior|regresa", t):
            return musica("anterior")

    if "volumen" in t or "silencia" in t:
        if re.search(r"sube|aumenta|más alto", t):
            return volumen("subir")
        if re.search(r"baja|disminuye|más bajo", t):
            return volumen("bajar")
        if re.search(r"silencia|mute|quita el sonido", t):
            return volumen("silenciar")

    if "brillo" in t:
        if re.search(r"sube|aumenta|más alto", t):
            return brillo("subir")
        if re.search(r"baja|disminuye|más bajo", t):
            return brillo("bajar")
        return "Indica si quieres subir o bajar el brillo."

    tarea = re.search(
        r"\b(?:agrega|añade|crea|pon)\s+(?:una\s+)?tarea\s*(?:de|para|que|:)?\s*(.+)$",
        limpio,
        re.IGNORECASE,
    ) or re.search(
        r"\b(?:agrega|añade)\s+a\s+mi\s+lista\s+de\s+tareas\s*:?\s*(.+)$",
        limpio,
        re.IGNORECASE,
    )
    if tarea:
        return agregar_tarea(tarea.group(1).strip())
    numero = re.search(r"tarea\s+(\d+)\s+(?:como\s+)?(?:hecha|lista|completada)", t)
    if numero:
        return completar_tarea(int(numero.group(1)))
    if re.search(r"qué tareas tengo|mis tareas|tareas pendientes", t):
        return listar_tareas()

    nota = re.search(
        r"\b(?:anota|apunta|(?:crea|agrega|añade|guarda) una nota)\s*(?:que|de|:)?\s*(.+)$",
        limpio,
        re.IGNORECASE,
    )
    if nota:
        return agregar_nota(nota.group(1).strip())
    if re.search(r"qué notas tengo|mis notas|lee mis notas", t):
        return listar_notas()

    return None