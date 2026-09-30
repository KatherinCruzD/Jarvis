from ai import gemini_client, ollama_client

PROVEEDORES = {
    "local": ollama_client.preguntar,
    "gemini": gemini_client.preguntar,
}

def responder(pregunta: str, proveedor: str = "local") -> str:
    if proveedor not in PROVEEDORES:
        return f"No conozco el proveedor '{proveedor}'."
    try:
        return PROVEEDORES[proveedor](pregunta)
    except Exception as error:
        return f"Tuve un problema con '{proveedor}': {error}"