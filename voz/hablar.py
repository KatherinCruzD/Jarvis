import ctypes
import json
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_candado = threading.Lock()

CARPETA_JARVIS = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Jarvis"
CARPETA_VOCES = CARPETA_JARVIS / "voces"
ARCHIVO_PREFERENCIA = CARPETA_JARVIS / "voz.json"
MOTORES = ("windows", "piper", "edge", "auto")
NOMBRES = {
    "windows": "voz de Windows, sin internet",
    "piper": "voz neuronal local, sin internet",
    "edge": "voz natural, con internet",
    "auto": "automática: la natural si hay internet y, si no, la local",
}
PIPER_PREDETERMINADA = "es_ES-davefx-medium"
EDGE_PREDETERMINADA = "es-CO-GonzaloNeural"

_voz_piper = None
_voz_piper_nombre = None


def limpiar(texto: str) -> str:
    texto = re.sub(r"[*#`_>]", "", texto)
    return texto.strip()


def _hay_internet() -> bool:
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=1.0):
            return True
    except OSError:
        return False


def motor_preferido() -> str:
    """La elección guardada con «cambia la voz» manda sobre JARVIS_VOZ del .env."""
    try:
        guardado = json.loads(ARCHIVO_PREFERENCIA.read_text(encoding="utf-8"))
        if guardado.get("motor") in MOTORES:
            return guardado["motor"]
    except (OSError, ValueError, AttributeError):
        pass
    modo = os.getenv("JARVIS_VOZ", "windows").strip().lower()
    return modo if modo in MOTORES else "windows"


def elegir_motor(nombre: str) -> None:
    if nombre not in MOTORES:
        raise ValueError(f"Voz desconocida: {nombre}")
    CARPETA_JARVIS.mkdir(parents=True, exist_ok=True)
    ARCHIVO_PREFERENCIA.write_text(json.dumps({"motor": nombre}), encoding="utf-8")


def piper_disponible() -> bool:
    nombre = os.getenv("JARVIS_VOZ_PIPER", PIPER_PREDETERMINADA).strip()
    return (CARPETA_VOCES / f"{nombre}.onnx").exists()


def _motores(detener) -> list:
    # Si ya llegó cancelada no vale la pena sintetizar una voz neural.
    if detener is not None and detener.is_set():
        return ["windows"]
    modo = motor_preferido()
    if modo == "auto":
        return (["edge"] if _hay_internet() else []) + ["piper", "windows"]
    if modo == "edge":
        return ["edge", "piper", "windows"]
    if modo == "piper":
        return ["piper", "windows"]
    return ["windows"]


def hablar(texto: str, detener: threading.Event | None = None) -> None:
    texto = limpiar(texto)
    if not texto:
        return

    with _candado:
        for motor in _motores(detener):
            try:
                print(f"[voz] hablando con: {motor}")
                if motor == "edge":
                    _hablar_edge(texto, detener)
                elif motor == "piper":
                    _hablar_piper(texto, detener)
                else:
                    _hablar_windows(texto, detener)
                return
            except Exception as error:
                if motor == "windows":
                    raise
                print(f"[voz] {motor} no pudo hablar ({error}); uso otra voz.")


# ---------- Utilidades de audio ----------

def _archivo_temporal(sufijo: str) -> str:
    descriptor, ruta = tempfile.mkstemp(suffix=sufijo)
    os.close(descriptor)
    return ruta


def _borrar(ruta: str) -> None:
    try:
        os.remove(ruta)
    except OSError:
        pass


def _mci(orden: str):
    memoria = ctypes.create_unicode_buffer(256)
    codigo = ctypes.windll.winmm.mciSendStringW(orden, memoria, 255, 0)
    return codigo, memoria.value


def _reproducir(ruta: str, detener) -> None:
    if os.name != "nt":
        raise RuntimeError("La reproducción de audio solo está disponible en Windows.")
    tipo = "waveaudio" if ruta.lower().endswith(".wav") else "mpegvideo"
    alias = f"jarvisvoz{threading.get_ident()}"
    codigo, _ = _mci(f'open "{ruta}" type {tipo} alias {alias}')
    if codigo:
        raise RuntimeError(f"No pude abrir el audio (código {codigo}).")
    try:
        _mci(f"play {alias}")
        time.sleep(0.15)
        while True:
            if detener is not None and detener.is_set():
                _mci(f"stop {alias}")
                return
            codigo, estado = _mci(f"status {alias} mode")
            if codigo or estado != "playing":
                return
            time.sleep(0.05)
    finally:
        _mci(f"close {alias}")


def _con_limite(funcion, segundos: float) -> None:
    resultado = {}

    def trabajo():
        try:
            funcion()
        except Exception as error:
            resultado["error"] = error

    hilo = threading.Thread(target=trabajo, daemon=True)
    hilo.start()
    hilo.join(segundos)
    if hilo.is_alive():
        raise TimeoutError("tardó demasiado")
    if "error" in resultado:
        raise resultado["error"]


# ---------- Motor 1: voces de Windows (sin internet) ----------

def _hablar_windows(texto: str, detener) -> None:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as archivo:
        archivo.write(texto)
        ruta = archivo.name

    ruta_segura = ruta.replace("'", "''")
    elegida = os.getenv("JARVIS_VOZ_WINDOWS", "").strip().replace("'", "''")
    if elegida:
        filtro = f"$_.VoiceInfo.Name -like '*{elegida}*'"
    else:
        filtro = "$_.VoiceInfo.Culture.Name -like 'es*'"
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$v = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$es = $v.GetInstalledVoices() | "
        f"Where-Object {{ {filtro} }} | "
        "Select-Object -First 1; "
        "if ($es) { $v.SelectVoice($es.VoiceInfo.Name) }; "
        f"$v.Speak((Get-Content -Raw -Encoding UTF8 -LiteralPath '{ruta_segura}'))"
    )

    try:
        proceso = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", script],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        while proceso.poll() is None:
            if detener is not None and detener.is_set():
                try:
                    proceso.terminate()
                except ProcessLookupError:
                    pass
                try:
                    proceso.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proceso.kill()
                    proceso.wait()
                return
            time.sleep(0.05)
        if proceso.returncode:
            raise subprocess.CalledProcessError(proceso.returncode, proceso.args)
    finally:
        _borrar(ruta)


# ---------- Motor 2: Piper, voz neuronal local (sin internet) ----------

def _cargar_piper():
    global _voz_piper, _voz_piper_nombre
    nombre = os.getenv("JARVIS_VOZ_PIPER", PIPER_PREDETERMINADA).strip()
    if _voz_piper is None or _voz_piper_nombre != nombre:
        from piper import PiperVoice

        modelo = CARPETA_VOCES / f"{nombre}.onnx"
        if not modelo.exists():
            raise FileNotFoundError(
                f"falta la voz {nombre}; descárgala con: "
                f'python -m piper.download_voices {nombre} --download-dir "{CARPETA_VOCES}"'
            )
        _voz_piper = PiperVoice.load(modelo)
        _voz_piper_nombre = nombre
    return _voz_piper


def _hablar_piper(texto: str, detener) -> None:
    voz = _cargar_piper()
    ruta = _archivo_temporal(".wav")
    try:
        with wave.open(ruta, "wb") as archivo:
            voz.synthesize_wav(texto, archivo)
        if detener is not None and detener.is_set():
            return
        _reproducir(ruta, detener)
    finally:
        _borrar(ruta)


# ---------- Motor 3: edge-tts, voz natural (necesita internet) ----------

def _hablar_edge(texto: str, detener) -> None:
    import edge_tts

    nombre = os.getenv("JARVIS_VOZ_EDGE", EDGE_PREDETERMINADA).strip()
    ruta = _archivo_temporal(".mp3")
    try:
        _con_limite(lambda: edge_tts.Communicate(texto, nombre).save_sync(ruta), 15)
        if os.path.getsize(ruta) == 0:
            raise RuntimeError("el servicio no devolvió audio")
        if detener is not None and detener.is_set():
            return
        _reproducir(ruta, detener)
    finally:
        _borrar(ruta)