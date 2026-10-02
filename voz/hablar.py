import os
import re
import subprocess
import tempfile
import threading
import time

_candado = threading.Lock()


def limpiar(texto: str) -> str:
    texto = re.sub(r"[*#`_>]", "", texto)
    return texto.strip()


def hablar(texto: str, detener: threading.Event | None = None) -> None:
    texto = limpiar(texto)
    if not texto:
        return

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as archivo:
        archivo.write(texto)
        ruta = archivo.name

    ruta_segura = ruta.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$v = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$es = $v.GetInstalledVoices() | "
        "Where-Object { $_.VoiceInfo.Culture.Name -like 'es*' } | "
        "Select-Object -First 1; "
        "if ($es) { $v.SelectVoice($es.VoiceInfo.Name) }; "
        f"$v.Speak((Get-Content -Raw -Encoding UTF8 -LiteralPath '{ruta_segura}'))"
    )

    try:
        with _candado:
            proceso = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", script],
                creationflags=subprocess.CREATE_NO_WINDOW,
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
        if os.path.exists(ruta):
            os.remove(ruta)