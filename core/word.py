import re
import unicodedata


def _normalizar(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(
        caracter
        for caracter in normalizado
        if not unicodedata.combining(caracter)
    )


def interpretar_formato_apa(texto: str) -> bool:
    limpio = " ".join(_normalizar(texto).strip(" \t\r\n.,!?¡¿").split())
    limpio = re.sub(r"^jarvis\s*[,.:;-]\s*", "jarvis ", limpio)
    limpio = re.sub(r"\bedicion\s+(?=7\b)", "", limpio)
    orden = re.fullmatch(
        r"(?:jarvis\s+)?(?:por\s+favor\s+)?"
        r"(?:pon(?:er|me|le)?|aplica(?:r)?|formatea(?:r)?)\s+(.+)",
        limpio,
    )
    if orden is None:
        return False

    instruccion = orden.group(1)
    if re.search(r"\b(?:todos|todas|cada|varios|varias)\b", instruccion):
        return False
    menciona_apa = re.search(
        r"\b(?:normas?\s+apa|formato\s+apa|documento\b.*\bapa|"
        r"\bapa\s+(?:7|septima))\b",
        instruccion,
    )
    return menciona_apa is not None


def interpretar_portada_apa(texto: str) -> str | None:
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:;-]*)?"
        r"(?:crea|haz|genera|agrega|pon(?:me)?)\s+"
        r"(?:una\s+)?portada\s+(?:apa\s+)?(?:con\s+)?"
        r"(?:el\s+)?t[ií]tulo\s*[:,-]?\s*(.+?)\s*[.!?]*\s*",
        texto,
        flags=re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    titulo = coincidencia.group(1).strip(" \t\"'")
    return titulo if titulo else None


def interpretar_formato_elemento_apa(texto: str) -> str | None:
    limpio = _normalizar(texto).strip()
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:;-]*)?"
        r"(?:aplica|pon(?:le)?|formatea)\s+"
        r"(?:las?\s+)?(?:normas?\s+)?(?:formato\s+)?apa(?:\s*7)?\s+"
        r"(?:a|al|a la)\s+(?:esta\s+|la\s+)?(tabla|imagen|figura)"
        r"(?:\s+seleccionada)?\s*[.!?]*\s*",
        limpio,
        flags=re.IGNORECASE,
    )
    return coincidencia.group(1) if coincidencia else None


def interpretar_seccion_documento(texto: str) -> str | None:
    limpio = " ".join(_normalizar(texto).strip().split())
    coincidencia = re.fullmatch(
        r"\s*(?:jarvis[\s,:;-]*)?"
        r"(?:crea|redacta|escribe|genera|prepara|hazme)\s+"
        r"(?:el\s+|la\s+|los\s+|las\s+)?(introduccion|objetivos?|conclusiones?)"
        r"(?:\s+(?:del|de la|para el|para la)\s+"
        r"(?:documento|trabajo|archivo|texto)(?:\s+actual|abierto)?)?"
        r"\s*[.!?]*\s*",
        limpio,
        flags=re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    seccion = coincidencia.group(1)
    if seccion == "introduccion":
        return "Introducción"
    if seccion.startswith("objetivo"):
        return "Objetivos"
    return "Conclusiones"


def interpretar_texto_documento(texto: str) -> str | None:
    prefijo = r"\s*(?:jarvis[\s,:;-]*)?(?:por\s+favor\s+)?"
    verbos = r"(?:escribe|escribir|anota|agrega|añade|pon|poner|inserta|insertar)"
    patrones = (
        prefijo
        + verbos
        + r"\s+(?:en\s+)?(?:el|mi)\s+documento"
        + r"(?:\s+de\s+word)?"
        + r"(?:\s+(?:que\s+diga|lo\s+siguiente|este\s+texto|el\s+texto|"
        + r"el\s+siguiente\s+texto))?"
        + r"\s*[:,-]?\s*(.+?)\s*",
        prefijo
        + verbos
        + r"\s+(.+?)\s+(?:en|dentro\s+de)\s+(?:el|mi)\s+documento"
        + r"(?:\s+de\s+word)?\s*[.!?]*\s*",
    )
    contenido = None
    for patron in patrones:
        coincidencia = re.fullmatch(
            patron,
            texto,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if coincidencia is not None:
            contenido = coincidencia.group(1).strip()
            break
    if contenido is None:
        return None
    for apertura, cierre in (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’")):
        if contenido.startswith(apertura) and contenido.endswith(cierre):
            if len(contenido) >= 2:
                contenido = contenido[len(apertura) : -len(cierre)].strip()
            break
    if not contenido:
        return None
    return contenido


def _documento_activo():
    try:
        import pythoncom
        import win32com.client
    except ImportError as error:
        raise RuntimeError(
            "Falta pywin32 para conectar Jarvis con Microsoft Word. "
            "Instala las dependencias del proyecto."
        ) from error

    inicializado = False
    try:
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            inicializado = True
        except pythoncom.error as error:
            if error.hresult != -2147417850:
                raise
        try:
            word = win32com.client.GetActiveObject("Word.Application")
        except Exception as error:
            raise RuntimeError(
                "No pude conectarme a Word. Abre Word y el documento que quieres editar."
            ) from error
        if word.Documents.Count == 0:
            raise RuntimeError("Word está abierto, pero no hay ningún documento abierto.")
        return pythoncom, inicializado, word, word.ActiveDocument
    except Exception:
        if inicializado:
            pythoncom.CoUninitialize()
        raise


def nombre_documento_activo() -> str:
    pythoncom, inicializado, _word, documento = _documento_activo()
    try:
        return documento.Name
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def _formatear_documento(documento) -> None:
    contenido = documento.Content
    contenido.Font.Name = "Times New Roman"
    contenido.Font.Size = 12
    parrafos = contenido.ParagraphFormat
    parrafos.Alignment = 0
    parrafos.LineSpacingRule = 2
    parrafos.SpaceBefore = 0
    parrafos.SpaceAfter = 0
    parrafos.FirstLineIndent = 36

    for seccion in documento.Sections:
        pagina = seccion.PageSetup
        pagina.PaperSize = 2
        pagina.TopMargin = 72
        pagina.BottomMargin = 72
        pagina.LeftMargin = 72
        pagina.RightMargin = 72
        numeros = seccion.Headers.Item(1).PageNumbers
        if numeros.Count == 0:
            numeros.Add(2, True)


def aplicar_formato_apa() -> str:
    pythoncom, inicializado, word, documento = _documento_activo()
    try:
        _formatear_documento(documento)
        return (
            f"Apliqué el formato general APA 7 a «{documento.Name}». "
            "No agregué texto ni guardé el archivo; revisa y guarda los cambios."
        )
    except Exception as error:
        raise RuntimeError(f"Word no pudo aplicar el formato APA: {error}") from error
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def leer_documento_activo() -> tuple[str, str]:
    pythoncom, inicializado, _word, documento = _documento_activo()
    try:
        contenido = documento.Content.Text.strip()
        if not contenido:
            raise RuntimeError(
                "El documento activo está vacío; agrega contenido para que pueda "
                "preparar una sección coherente."
            )
        if len(contenido) > 20000:
            contenido = contenido[:20000]
        return documento.Name, contenido
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def insertar_seccion_documento(
    titulo: str, contenido: str, nombre_documento: str
) -> str:
    if titulo not in {"Introducción", "Objetivos", "Conclusiones"}:
        raise ValueError("La sección solicitada no está permitida.")
    if not contenido.strip() or len(contenido) > 12000:
        raise ValueError("El texto de la sección está vacío o supera el límite.")

    pythoncom, inicializado, _word, documento = _documento_activo()
    try:
        return _insertar_seccion(documento, titulo, contenido, nombre_documento)
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Word no pudo insertar la sección: {error}") from error
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def insertar_texto_documento(
    contenido: str, nombre_documento: str | None = None
) -> str:
    contenido = contenido.strip()
    if not contenido or len(contenido) > 10000:
        raise ValueError("El texto debe tener entre 1 y 10000 caracteres.")
    pythoncom, inicializado, _word, documento = _documento_activo()
    try:
        if nombre_documento is not None and documento.Name != nombre_documento:
            raise RuntimeError(
                "El documento activo cambió antes de insertar el texto. "
                "Vuelve a solicitarlo desde el documento correcto."
            )
        _formatear_documento(documento)
        texto_word = contenido.replace("\r\n", "\n").replace("\r", "\n")
        texto_word = texto_word.replace("\n", "\r")
        contenido_actual = documento.Content.Text
        punto_insercion = documento.Content.End - 1
        prefijo = "" if not contenido_actual.strip() else "\r"
        texto_insertado = f"{prefijo}{texto_word}"
        documento.Range(punto_insercion, punto_insercion).InsertAfter(
            texto_insertado
        )

        inicio_texto = punto_insercion + len(prefijo)
        rango_insertado = documento.Range(
            inicio_texto,
            inicio_texto + len(texto_word),
        )
        rango_insertado.Font.Name = "Times New Roman"
        rango_insertado.Font.Size = 12
        rango_insertado.ParagraphFormat.Alignment = 0
        rango_insertado.ParagraphFormat.LineSpacingRule = 2
        rango_insertado.ParagraphFormat.FirstLineIndent = 36
        rango_insertado.ParagraphFormat.SpaceBefore = 0
        rango_insertado.ParagraphFormat.SpaceAfter = 0
        return (
            f"Escribí tu texto al final de «{documento.Name}» con formato "
            "APA 7 (Times New Roman 12, doble espacio y sangría). "
            "No guardé el documento; revísalo y guárdalo."
        )
    except Exception as error:
        if isinstance(error, (RuntimeError, ValueError)):
            raise
        raise RuntimeError(f"Word no pudo escribir el texto: {error}") from error
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def _insertar_seccion(documento, titulo: str, contenido: str, nombre_documento: str) -> str:
    if documento.Name != nombre_documento:
        raise RuntimeError(
            "El documento activo cambió mientras preparaba el texto. "
            "Vuelve a solicitarlo desde el documento correcto."
        )
    punto_insercion = documento.Content.End - 1
    rango = documento.Range(punto_insercion, punto_insercion)
    rango.InsertAfter(f"\r{titulo}\r{contenido.strip()}\r")
    rango.Font.Name = "Times New Roman"
    rango.Font.Size = 12
    rango.ParagraphFormat.LineSpacingRule = 2
    rango.ParagraphFormat.Alignment = 0
    rango.ParagraphFormat.FirstLineIndent = 36
    parrafo_titulo = documento.Paragraphs.Item(documento.Paragraphs.Count - 2)
    parrafo_titulo.Range.Font.Bold = True
    parrafo_titulo.Range.ParagraphFormat.FirstLineIndent = 0
    parrafo_titulo.Range.ParagraphFormat.KeepWithNext = True
    return (
        f"Añadí «{titulo}» al final de «{documento.Name}». "
        "Revisa el texto y guarda los cambios."
    )


def aplicar_apa_a_elemento(tipo: str) -> str:
    if tipo not in {"tabla", "imagen", "figura"}:
        raise ValueError("Solo se puede aplicar este formato a una tabla o imagen.")
    pythoncom, inicializado, word, documento = _documento_activo()
    try:
        seleccion = word.Selection
        if tipo == "tabla":
            if seleccion.Tables.Count == 0:
                raise RuntimeError(
                    "Selecciona una celda de la tabla en Word y vuelve a pedir "
                    "que aplique formato APA."
                )
            tabla = seleccion.Tables.Item(1)
            return _aplicar_apa_tabla(documento, tabla)

        if seleccion.InlineShapes.Count == 0 and seleccion.ShapeRange.Count == 0:
            raise RuntimeError(
                "Selecciona la imagen en Word y vuelve a pedir que aplique formato APA."
            )
        if seleccion.InlineShapes.Count:
            imagen = seleccion.InlineShapes.Item(1)
        else:
            imagen = seleccion.ShapeRange.Item(1).ConvertToInlineShape()
        return _aplicar_apa_imagen(documento, imagen, seleccion.ParagraphFormat)
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(
            f"Word no pudo aplicar formato APA a la {tipo}: {error}"
        ) from error
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def _aplicar_apa_tabla(documento, tabla) -> str:
    tabla.Range.Font.Name = "Times New Roman"
    tabla.Range.Font.Size = 12
    tabla.Range.ParagraphFormat.Alignment = 0
    tabla.Range.ParagraphFormat.LineSpacingRule = 2
    tabla.Range.ParagraphFormat.FirstLineIndent = 0
    tabla.Rows.Alignment = 1
    tabla.Borders.Enable = 0
    for borde in (-1, -3):
        tabla.Borders.Item(borde).LineStyle = 1
    if tabla.Rows.Count:
        tabla.Rows.Item(1).HeadingFormat = True
        tabla.Rows.Item(1).Borders.Item(-3).LineStyle = 1
    return (
        f"Apliqué formato APA a la tabla seleccionada en «{documento.Name}». "
        "Añade o revisa su número, título y nota; no guardé el documento."
    )


def _aplicar_apa_imagen(documento, imagen, parrafo) -> str:
    imagen.LockAspectRatio = -1
    if imagen.Width > 468:
        imagen.Width = 468
    parrafo.Alignment = 1
    parrafo.FirstLineIndent = 0
    parrafo.LineSpacingRule = 0
    return (
        f"Centré la imagen seleccionada y ajusté su ancho al área de escritura "
        f"APA en «{documento.Name}». Añade o revisa el número, título y nota "
        "de figura; no guardé el documento."
    )


def insertar_portada_apa(titulo: str) -> str:
    titulo = titulo.strip()
    if not titulo or len(titulo) > 300:
        raise ValueError("El título debe tener entre 1 y 300 caracteres.")
    pythoncom, inicializado, word, documento = _documento_activo()
    try:
        return _insertar_portada(documento, titulo)
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Word no pudo crear la portada APA: {error}") from error
    finally:
        if inicializado:
            pythoncom.CoUninitialize()


def _insertar_portada(documento, titulo: str) -> str:
    if documento.Content.Text.strip():
        raise RuntimeError(
            "Para crear una portada sin sobrescribir contenido, abre un "
            "documento en blanco en Word y vuelve a intentarlo."
        )

    rango = documento.Range(0, 0)
    rango.Text = (
        "\r\r\r\r\r"
        f"{titulo}\r"
        "[Nombre del estudiante]\r"
        "[Institución]\r"
        "[Curso y sección]\r"
        "[Nombre del docente]\r"
        "[Fecha de entrega]\r"
    )
    contenido = documento.Content
    contenido.Font.Name = "Times New Roman"
    contenido.Font.Size = 12
    contenido.ParagraphFormat.Alignment = 1
    contenido.ParagraphFormat.LineSpacingRule = 2
    contenido.ParagraphFormat.SpaceBefore = 0
    contenido.ParagraphFormat.SpaceAfter = 0
    texto_titulo = documento.Paragraphs.Item(6).Range
    texto_titulo.Font.Bold = True
    texto_titulo.ParagraphFormat.KeepWithNext = True
    fin_portada = documento.Content
    fin_portada.Collapse(0)
    fin_portada.InsertBreak(7)
    return (
        f"Creé la portada APA 7 para «{titulo}» en «{documento.Name}». "
        "Completa los datos entre corchetes y guarda el documento."
    )
