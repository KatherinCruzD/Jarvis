import ollama

MODELO = "llama3.2:3b"
INSTRUCCION = "Eres Jarvis, un asistente personal amable y claro. Responde siempre en español."

def preguntar(
    pregunta: str,
    historial: list[dict[str, str]] | None = None,
    contexto: list[str] | None = None,
) -> str:
    instruccion = INSTRUCCION
    if contexto:
        recuerdos = "\n".join(f"- {recuerdo}" for recuerdo in contexto)
        instruccion += (
            "\nUsa estos recuerdos guardados localmente solo si son relevantes. "
            "No inventes otros recuerdos ni los presentes como información recién verificada:\n"
            f"{recuerdos}"
        )
    mensajes = [{"role": "system", "content": instruccion}]
    if historial:
        mensajes.extend(historial)
    mensajes.append({"role": "user", "content": pregunta})
    respuesta = ollama.chat(
        model=MODELO,
        messages=mensajes,
    )
    return respuesta["message"]["content"]