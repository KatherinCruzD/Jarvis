import subprocess
import webbrowser

SITIOS = {
    "gmail": "https://mail.google.com",
    "tiktok": "https://www.tiktok.com",
    "whatsapp": "https://web.whatsapp.com",
    "spotify": "https://open.spotify.com",
}

PROGRAMAS = {
    "word": "winword",
    "vscode": "code",
}

def ejecutar_atajo(nombre: str) -> str:
    if nombre in SITIOS:
        webbrowser.open(SITIOS[nombre])
        return f"Abriendo {nombre}."
    if nombre in PROGRAMAS:
        subprocess.Popen(
            ["cmd", "/c", "start", "", PROGRAMAS[nombre]],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return f"Abriendo {nombre}."
    return f"No conozco el atajo '{nombre}'."