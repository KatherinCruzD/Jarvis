import os
import re
import subprocess
import tempfile
import threading

_candado = threading.Lock()

def limpiar(texto: str) -> str:
    texto = re.sub(r"[*#`_>]", "", texto)
    return texto.strip()


def hablar(texto: str) -> None:
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
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    finally:
        os.remove(ruta)