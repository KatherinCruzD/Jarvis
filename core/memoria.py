import os
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

MAXIMO_RECUERDOS = 500
MAXIMO_TEXTO = 1000
PALABRAS_VACIAS = {
    "acerca",
    "algo",
    "como",
    "cual",
    "cuando",
    "donde",
    "el",
    "ella",
    "ellos",
    "en",
    "es",
    "esa",
    "ese",
    "esta",
    "este",
    "fue",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "que",
    "recuerdas",
    "sobre",
    "un",
    "una",
    "y",
}


def ruta_memoria() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / "Jarvis" / "memoria.sqlite3"


def _normalizar(texto: str) -> str:
    ascii_texto = unicodedata.normalize("NFKD", texto.casefold())
    sin_acentos = "".join(
        caracter for caracter in ascii_texto if not unicodedata.combining(caracter)
    )
    return " ".join(re.findall(r"[a-z0-9]+", sin_acentos))


def _palabras(texto: str) -> set[str]:
    return {
        palabra
        for palabra in _normalizar(texto).split()
        if len(palabra) > 2 and palabra not in PALABRAS_VACIAS
    }


def _conectar() -> sqlite3.Connection:
    ruta = ruta_memoria()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta, timeout=5)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS recuerdos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL,
            normalizado TEXT NOT NULL UNIQUE,
            creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conexion


def recordar(texto: str) -> str:
    contenido = texto.strip().strip(" .!?¿¡\"'")
    normalizado = _normalizar(contenido)
    if len(contenido) < 3:
        return "Dime con más detalle qué quieres que recuerde."
    if len(contenido) > MAXIMO_TEXTO:
        return f"El recuerdo es muy largo; el límite es {MAXIMO_TEXTO} caracteres."
    if not _palabras(contenido):
        return "No encontré información suficiente para guardar como recuerdo."

    with closing(_conectar()) as conexion, conexion:
        existente = conexion.execute(
            "SELECT id FROM recuerdos WHERE normalizado = ?",
            (normalizado,),
        ).fetchone()
        if existente:
            conexion.execute(
                "UPDATE recuerdos SET texto = ?, creado = CURRENT_TIMESTAMP WHERE id = ?",
                (contenido, existente[0]),
            )
            return f"Actualicé este recuerdo: {contenido}"

        cantidad = conexion.execute("SELECT COUNT(*) FROM recuerdos").fetchone()[0]
        if cantidad >= MAXIMO_RECUERDOS:
            return (
                "La memoria llegó al límite de 500 recuerdos. "
                "Pídeme que olvide alguno antes de guardar otro."
            )
        conexion.execute(
            "INSERT INTO recuerdos (texto, normalizado) VALUES (?, ?)",
            (contenido, normalizado),
        )
    return f"Lo recordaré: {contenido}"


def buscar(texto: str, limite: int = 3) -> list[str]:
    consulta = _palabras(texto)
    if not consulta:
        return []
    with closing(_conectar()) as conexion, conexion:
        recuerdos = conexion.execute(
            "SELECT texto FROM recuerdos ORDER BY creado DESC, id DESC LIMIT ?",
            (MAXIMO_RECUERDOS,),
        ).fetchall()

    puntuados: list[tuple[int, int, str]] = []
    for indice, (contenido,) in enumerate(recuerdos):
        coincidencias = len(consulta & _palabras(contenido))
        if coincidencias:
            puntuados.append((coincidencias, -indice, contenido))
    puntuados.sort(reverse=True)
    return [contenido for _, _, contenido in puntuados[:limite]]


def listar(limite: int = 10) -> list[str]:
    if not 1 <= limite <= MAXIMO_RECUERDOS:
        raise ValueError(
            f"El límite de recuerdos debe estar entre 1 y {MAXIMO_RECUERDOS}."
        )
    with closing(_conectar()) as conexion, conexion:
        filas = conexion.execute(
            "SELECT texto FROM recuerdos ORDER BY creado DESC, id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [texto for (texto,) in filas]


def olvidar(texto: str) -> str:
    contenido = texto.strip().strip(" .!?¿¡\"'")
    normalizado = _normalizar(contenido)
    if not normalizado:
        return "Dime exactamente qué recuerdo quieres que olvide."
    with closing(_conectar()) as conexion, conexion:
        cursor = conexion.execute(
            "DELETE FROM recuerdos WHERE normalizado = ?",
            (normalizado,),
        )
    if cursor.rowcount:
        return f"Olvidé este recuerdo: {contenido}"
    return (
        "No encontré un recuerdo idéntico. Pídeme que te muestre lo que recuerdo "
        "y dime el recuerdo exacto que quieres borrar."
    )


def interpretar_recuerdo(texto: str) -> str | None:
    coincidencia = re.fullmatch(
        r"\s*recuerda(?:\s+que)?\s*[:,-]?\s*(.+?)\s*[.!?]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    return coincidencia.group(1).strip() if coincidencia else None


def interpretar_consulta_memoria(texto: str) -> str | None:
    texto = texto.strip().lstrip("¿¡").strip()
    coincidencia = re.fullmatch(
        r"\s*(?:qu[eé]\s+recuerdas(?:\s+de\s+(.+?))?|"
        r"mu[eé]strame\s+(?:mis\s+)?recuerdos|"
        r"lista\s+(?:mis\s+)?recuerdos)"
        r"\s*[?!.]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    return (coincidencia.group(1) or "").strip()


def interpretar_olvidar(texto: str) -> str | None:
    coincidencia = re.fullmatch(
        r"\s*olvida(?:\s+exactamente)?(?:\s+que)?\s*[:,-]?\s*(.+?)\s*[.!?]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    return coincidencia.group(1).strip() if coincidencia else None
