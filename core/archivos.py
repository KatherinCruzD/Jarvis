import os
import re
import logging
from pathlib import Path

MAXIMO_RESULTADOS = 8
PROFUNDIDAD_MAXIMA = 6
DIRECTORIOS_OMITIDOS = {
    "$recycle.bin",
    "appdata",
    "application data",
    "configuración local",
    "cookies",
    "datos de programa",
    "entorno de red",
    "impresoras",
    "mi música",
    "mis imágenes",
    "mis vídeos",
    "menú inicio",
    "mis documentos",
    "node_modules",
    "plantillas",
    "reciente",
    "sendto",
    "system volume information",
}


def interpretar_busqueda(texto: str) -> str | None:
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:;-]*)?(?:busca(?:r)?|encuentra(?:me)?)\s+"
        r"(?:(?:en\s+el\s+)?explorador\s+de\s+archivos\s*,?\s*)?"
        r"(?:(?:un|una|el|la)\s+)?(?:archivo|documento)"
        r"(?:\s+(?:llamado|llamada|que\s+se\s+llama))?"
        r"\s*[:,-]?\s*(.+?)\s*[.!?]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    return coincidencia.group(1).strip(" \"'") if coincidencia else None


def interpretar_apertura(texto: str) -> tuple[str, str | None] | None:
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:;-]*)?abre\s+(?:un\s+|el\s+)?"
        r"(?:archivo|documento)"
        r"(?:\s+(?:llamado|llamada|que\s+se\s+llama))?"
        r"\s*[:,-]?\s*(.+?)"
        r"(?:\s+(?:en|dentro\s+de)\s+(?:la\s+)?carpeta\s+(.+?))?"
        r"\s*[.!?]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    nombre = coincidencia.group(1).strip(" \"'")
    carpeta = coincidencia.group(2)
    return nombre, carpeta.strip(" \"'") if carpeta else None


def interpretar_crear_carpeta_drive(texto: str) -> str | None:
    patrones = (
        r"\s*crea(?:r)?\s+(?:una\s+)?carpeta\s+"
        r"(?:en\s+(?:google\s+)?drive\s+)?"
        r"(?:llamada?(?:\s+como)?|con nombre)"
        r"\s*[:,-]?\s*(.+?)(?:\s+en\s+(?:google\s+)?drive)?\s*[.!?]*\s*",
        r"\s*crea(?:r)?\s+(?:una\s+)?carpeta\s+(.+?)\s+"
        r"en\s+(?:google\s+)?drive\s*[.!?]*\s*",
    )
    for patron in patrones:
        coincidencia = re.fullmatch(patron, texto, flags=re.IGNORECASE)
        if coincidencia:
            return coincidencia.group(1).strip(" \"'")
    return None


def interpretar_subida_drive(texto: str) -> tuple[str, str | None] | None:
    patron = (
        r"\s*(?:sube|subir|carga|cargar)\s+"
        r"(?:a\s+(?:google\s+)?drive\s+)?"
        r"(?:el\s+)?archivo(?:\s+(?:llamado|llamada))?"
        r"\s*[:,-]?\s*(.+?)"
        r"(?:\s+(?:en|dentro\s+de)\s+(?:la\s+)?carpeta\s+(.+?))?"
        r"(?:\s+a\s+(?:google\s+)?drive)?\s*[.!?]*\s*"
    )
    coincidencia = re.fullmatch(patron, texto, flags=re.IGNORECASE)
    if coincidencia is None:
        return None
    nombre = coincidencia.group(1).strip(" \"'")
    carpeta = coincidencia.group(2)
    nombre = re.sub(
        r"\s+a\s+(?:google\s+)?drive$",
        "",
        nombre,
        flags=re.IGNORECASE,
    ).strip()
    return nombre, carpeta.strip(" \"'") if carpeta else None


def raices_archivos_personales() -> tuple[Path, ...]:
    valores: list[str] = []
    perfil = Path(os.environ.get("USERPROFILE", Path.home())).expanduser()
    valores.extend(
        str(perfil / nombre)
        for nombre in ("Desktop", "Documents", "Downloads", "OneDrive")
    )
    valores.extend(
        os.environ[nombre]
        for nombre in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")
        if os.environ.get(nombre)
    )
    try:
        import winreg

        clave_usuario = (
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave_usuario) as clave:
            for nombre in (
                "Desktop",
                "Personal",
                "{374DE290-123F-4565-9164-39C4925E467B}",
            ):
                try:
                    valor, _ = winreg.QueryValueEx(clave, nombre)
                except FileNotFoundError:
                    continue
                valores.append(os.path.expandvars(valor))
    except OSError:
        pass

    raices: list[Path] = []
    for valor in valores:
        raiz = Path(valor).expanduser()
        if raiz.is_dir():
            try:
                raiz = raiz.resolve()
            except OSError:
                continue
            if raiz not in raices:
                raices.append(raiz)
    return tuple(raices)


def raices_busqueda() -> tuple[Path, ...]:
    perfil = Path(os.environ.get("USERPROFILE", Path.home())).expanduser()
    raices = list(raices_archivos_personales())
    if perfil.is_dir():
        try:
            perfil_resuelto: Path | None = perfil.resolve()
        except OSError:
            perfil_resuelto = None
        if perfil_resuelto is not None and perfil_resuelto not in raices:
            raices.append(perfil_resuelto)

    raices.sort(key=lambda ruta: len(ruta.parts))
    raices_exteriores: list[Path] = []
    for raiz in raices:
        if not any(raiz == padre or padre in raiz.parents for padre in raices_exteriores):
            raices_exteriores.append(raiz)
    return tuple(raices_exteriores)


def buscar_archivos(nombre: str, limite: int = MAXIMO_RESULTADOS) -> list[Path]:
    consulta = nombre.strip().strip("\"'")
    if not consulta:
        raise ValueError("Indica el nombre del archivo que quieres buscar.")
    if len(consulta) > 180:
        raise ValueError("El nombre de búsqueda es demasiado largo.")
    if not 1 <= limite <= MAXIMO_RESULTADOS:
        raise ValueError(f"El límite debe estar entre 1 y {MAXIMO_RESULTADOS}.")

    termino = consulta.casefold()
    resultados_indice = _buscar_indice_windows(termino, limite)
    if resultados_indice:
        return resultados_indice

    resultados: list[Path] = []
    for raiz in raices_busqueda():
        for actual, directorios, archivos in os.walk(
            raiz,
            followlinks=False,
            onerror=lambda error: logging.warning(
                "No se pudo revisar la carpeta %s: %s", error.filename, error
            ),
        ):
            directorios[:] = [
                directorio
                for directorio in directorios
                if not directorio.startswith(".")
                and directorio.casefold() not in DIRECTORIOS_OMITIDOS
                and not (Path(actual) / directorio).is_symlink()
                and len(Path(actual, directorio).relative_to(raiz).parts)
                <= PROFUNDIDAD_MAXIMA
            ]
            for archivo in archivos:
                if termino in archivo.casefold():
                    resultados.append(Path(actual) / archivo)
                    if len(resultados) >= limite:
                        return resultados
    return resultados


def _buscar_indice_windows(termino: str, limite: int) -> list[Path]:
    if os.name != "nt":
        return []
    import pywintypes

    try:
        import win32com.client

        conexion = win32com.client.Dispatch("ADODB.Connection")
        conexion.Open(
            "Provider=Search.CollatorDSO;Extended Properties='Application=Windows';"
        )
        seguro = termino.replace("'", "''")
        consulta = (
            "SELECT System.ItemPathDisplay FROM SystemIndex "
            f"WHERE System.FileName LIKE '%{seguro}%'"
        )
        filas, _ = conexion.Execute(consulta)
        coincidencias: list[Path] = []
        while not filas.EOF and len(coincidencias) < limite:
            valor = filas.Fields.Item(0).Value
            if valor:
                ruta = Path(str(valor))
                if ruta.is_file():
                    coincidencias.append(ruta)
            filas.MoveNext()
        filas.Close()
        conexion.Close()
        return coincidencias
    except (OSError, pywintypes.com_error) as error:
        logging.info("El índice de Windows no está disponible; usaré búsqueda local: %s", error)
        return []


def buscar_archivo_exacto(nombre: str, carpeta: str | None = None) -> list[Path]:
    consulta = nombre.strip().strip("\"'")
    if not consulta:
        raise ValueError("Indica el nombre exacto del archivo.")
    resultados = buscar_archivos(consulta)
    if carpeta:
        resultados = [
            ruta for ruta in resultados if ruta.parent.name.casefold() == carpeta.casefold()
        ]
    if Path(consulta).suffix:
        return [ruta for ruta in resultados if ruta.name.casefold() == consulta.casefold()]
    return [
        ruta
        for ruta in resultados
        if ruta.name.casefold() == consulta.casefold()
        or ruta.stem.casefold() == consulta.casefold()
    ]


def abrir_archivo(nombre: str, carpeta: str | None = None) -> str:
    consulta = nombre.strip().strip("\"'")
    if not consulta:
        return "Dime el nombre exacto del archivo que quieres abrir."

    coincidencias = buscar_archivo_exacto(consulta, carpeta)
    if not coincidencias:
        return (
            f"No encontré un archivo llamado {consulta} en las carpetas de tu "
            "perfil de Windows ni en las ubicaciones conocidas de Escritorio, "
            "Documentos y Descargas."
        )
    if len(coincidencias) > 1:
        opciones = [
            f"{ruta.name}, en {ruta.parent.name or ruta.parent.drive}"
            for ruta in coincidencias[:5]
        ]
        return (
            "Encontré varios archivos. Di el nombre y la carpeta, por ejemplo "
            "'abre el archivo llamado reporte.pdf en la carpeta Finanzas': "
            + "; ".join(opciones)
        )

    ruta = coincidencias[0]
    try:
        os.startfile(str(ruta))
    except OSError as error:
        raise RuntimeError(f"No pude abrir {ruta.name}: {error}") from error
    return f"Abriendo {ruta.name}."


def buscar_y_describir(nombre: str) -> str:
    resultados = buscar_archivos(nombre)
    if not resultados:
        return (
            f"No encontré archivos que coincidan con {nombre} en las carpetas "
            "de tu perfil de Windows ni en Escritorio, Documentos o Descargas."
        )

    opciones = [
        f"{ruta.name}, en {ruta.parent.name or ruta.parent.drive}"
        for ruta in resultados[:5]
    ]
    total = len(resultados)
    respuesta = f"Encontré {total} archivo{'s' if total != 1 else ''}: " + "; ".join(
        opciones
    )
    if total > 5:
        respuesta += ". Hay más resultados; puedo mostrarte otros."
    return respuesta
