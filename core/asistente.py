from ai import gemini_client, ollama_client

PROVEEDORES = {
    "local": ollama_client.preguntar,
    "gemini": gemini_client.preguntar,
}


def responder(
    pregunta: str,
    proveedor: str = "local",
    historial: list[dict[str, str]] | None = None,
    contexto: list[str] | None = None,
) -> str:
    if proveedor not in PROVEEDORES:
        return f"No conozco el proveedor '{proveedor}'."
    try:
        return PROVEEDORES[proveedor](pregunta, historial, contexto)
    except Exception as error:
        return f"Tuve un problema con '{proveedor}': {error}"