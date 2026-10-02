import os
import re
import shutil
import subprocess
import unicodedata
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

SITIOS = {
    "gmail": ("Gmail", "https://mail.google.com"),
    "tiktok": ("TikTok", "https://www.tiktok.com"),
    "whatsapp": ("WhatsApp", "https://web.whatsapp.com"),
    "spotify": ("Spotify", "https://open.spotify.com"),
    "roblox": ("Roblox", "https://www.roblox.com"),
    "drive": ("Google Drive", "https://drive.google.com"),
}

PROGRAMAS = {
    "word": ("Microsoft Word", "winword"),
    "vscode": ("Visual Studio Code", "code"),
    "pseint": ("PSeInt", "pseint"),
}

ALIAS_ATAJOS = {
    "word": "word",
    "microsoft word": "word",
    "words": "word",
    "visual studio code": "vscode",
    "vs code": "vscode",
    "vs": "vscode",
    "vscode": "vscode",
    "visual studio": "vscode",
    "spotify": "spotify",
    "roblox": "roblox",
    "whatsapp": "whatsapp",
    "tik tok": "tiktok",
    "tiktok": "tiktok",
    "gmail": "gmail",
    "correo gmail": "gmail",
    "correo de gmail": "gmail",
    "mi correo gmail": "gmail",
    "mi correo de gmail": "gmail",
    "el correo gmail": "gmail",
    "el correo de gmail": "gmail",
    "mi gmail": "gmail",
    "correo": "outlook",
    "email": "outlook",
    "outlook": "outlook",
    "drive": "drive",
    "google drive": "drive",
    "pseint": "pseint",
    "pse int": "pseint",
}

APLICACIONES_WINDOWS = {
    "whatsapp": (
        "WhatsApp",
        "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
    ),
    "outlook": (
        "Outlook",
        "Microsoft.OutlookForWindows_8wekyb3d8bbwe!Microsoft.OutlookforWindows",
    ),
}


def describir_atajo(nombre: object) -> str | None:
    if not isinstance(nombre, str):
        return None
    if nombre in PROGRAMAS:
        return PROGRAMAS[nombre][0]
    if nombre in SITIOS:
        return SITIOS[nombre][0]
    if nombre in APLICACIONES_WINDOWS:
        return APLICACIONES_WINDOWS[nombre][0]
    return None


def interpretar_atajo(texto: str) -> str | None:
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    normalizado = "".join(
        caracter for caracter in normalizado if not unicodedata.combining(caracter)
    )
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:-]*)?"
        r"(?:abre(?:me)?|abrir|inicia(?:r)?|lanza(?:r)?|"
        r"entra(?:r)?\s+(?:a|en))\s+(.+?)\s*[.!?]*\s*",
        normalizado,
    )
    if coincidencia is None:
        return None
    return ALIAS_ATAJOS.get(coincidencia.group(1).strip())


def interpretar_spotify(texto: str) -> tuple[str, str] | None:
    patrones = (
        r"\s*(?:(?:jarvis)\s*[,.:;-]?\s*)?"
        r"(?:abre\s+)?spotify\s+(?:y\s+)?"
        r"(reproduce|pon|toca|busca)\s+(.+?)\s*[.!?]*\s*",
        r"\s*(?:(?:jarvis)\s*[,.:;-]?\s*)?"
        r"(reproduce|pon|toca|busca)\s+(.+?)\s+en\s+spotify\s*[.!?]*\s*",
    )
    for patron in patrones:
        coincidencia = re.fullmatch(patron, texto, flags=re.IGNORECASE)
        if coincidencia is not None:
            return (
                coincidencia.group(1).casefold(),
                coincidencia.group(2).strip(" \"'"),
            )
    return None


def interpretar_youtube(texto: str) -> tuple[str, str] | None:
    patrones = (
        r"\s*(?:(?:jarvis)\s*[,.:;-]?\s*)?"
        r"(?:abre\s+)?youtube\s+(?:y\s+)?"
        r"(reproduce|pon|toca|busca)\s+(.+?)\s*[.!?]*\s*",
        r"\s*(?:(?:jarvis)\s*[,.:;-]?\s*)?"
        r"(reproduce|pon|toca|busca)\s+(.+?)\s+en\s+youtube\s*[.!?]*\s*",
    )
    for patron in patrones:
        coincidencia = re.fullmatch(patron, texto, flags=re.IGNORECASE)
        if coincidencia is not None:
            return (
                coincidencia.group(1).casefold(),
                coincidencia.group(2).strip(" \"'"),
            )
    return None


def abrir_url_segura(url: str) -> None:
    if not url.startswith("https://"):
        raise ValueError("Solo se permiten direcciones web HTTPS.")
    try:
        os.startfile(url)
    except AttributeError:
        if not webbrowser.open(url, new=2):
            raise RuntimeError(f"No se pudo abrir {url}.")
    except OSError:
        if not webbrowser.open(url, new=2):
            raise RuntimeError(f"No se pudo abrir {url}.")


def abrir_busqueda_spotify(cancion: str) -> str:
    consulta = cancion.strip()
    if not consulta:
        return "Dime qué canción quieres buscar en Spotify."
    url = f"https://open.spotify.com/search/{quote_plus(consulta)}"
    abrir_url_segura(url)
    return (
        f"Abrí la búsqueda de {consulta} en Spotify. Selecciona la canción para "
        "reproducirla; la reproducción automática de Jarvis requiere la API oficial."
    )


def _resolver_ejecutable(nombre: str) -> Path:
    programas = os.environ.get("ProgramFiles", r"C:\Program Files")
    programas_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")

    candidatos: list[Path] = []
    if nombre == "word":
        candidatos.extend(
            Path(raiz) / ruta
            for raiz in (programas, programas_x86)
            for ruta in (
                r"Microsoft Office\root\Office16\WINWORD.EXE",
                r"Microsoft Office\Office16\WINWORD.EXE",
            )
        )
    elif nombre == "vscode":
        candidatos.extend(
            Path(raiz) / ruta
            for raiz in (local, programas, programas_x86)
            if raiz
            for ruta in (
                r"Programs\Microsoft VS Code\Code.exe",
                r"Microsoft VS Code\Code.exe",
            )
        )
        comando = shutil.which("code.cmd")
        if comando:
            candidatos.append(Path(comando).parent.parent / "Code.exe")
    elif nombre == "pseint":
        candidatos.extend(
            Path(raiz) / "PSeInt" / nombre_ejecutable
            for raiz in (programas, programas_x86)
            for nombre_ejecutable in ("pseint.exe", "PSeInt.exe")
        )
    elif nombre == "spotify":
        candidatos.extend(
            Path(raiz) / r"Spotify\Spotify.exe"
            for raiz in (roaming, local)
            if raiz
        )
        if local:
            candidatos.append(
                Path(local) / r"Microsoft\WindowsApps\Spotify.exe"
            )
    elif nombre == "roblox" and local:
        candidatos.extend(
            Path(version) / "RobloxPlayerBeta.exe"
            for version in Path(local, "Roblox", "Versions").glob("version-*")
        )
        candidatos.sort(key=lambda ruta: ruta.stat().st_mtime, reverse=True)
    else:
        raise ValueError(f"No se permite resolver el programa {nombre!r}.")

    localizado = shutil.which(PROGRAMAS.get(nombre, (None, None))[1] or "")
    if localizado:
        candidatos.append(Path(localizado))

    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    raise FileNotFoundError(
        f"No encontré el ejecutable de {PROGRAMAS.get(nombre, (nombre,))[0]} "
        "en sus ubicaciones habituales."
    )


def ejecutar_atajo(nombre: str) -> str:
    if nombre in APLICACIONES_WINDOWS:
        nombre_visible, app_id = APLICACIONES_WINDOWS[nombre]
        subprocess.Popen(
            ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return f"Abriendo {nombre_visible}."
    if nombre in PROGRAMAS or nombre in {"spotify", "roblox"}:
        try:
            ejecutable = _resolver_ejecutable(nombre)
        except FileNotFoundError:
            if nombre not in SITIOS:
                raise
        else:
            subprocess.Popen(
                [str(ejecutable)],
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return f"Abriendo {describir_atajo(nombre)}."
    if nombre in SITIOS:
        nombre_visible, url = SITIOS[nombre]
        abrir_url_segura(url)
        return f"Abriendo {nombre_visible}."
    return f"No conozco el atajo '{nombre}'."