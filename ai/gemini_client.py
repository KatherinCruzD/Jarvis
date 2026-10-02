import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODELO = "gemini-3.8-flash"
INSTRUCCION = "Eres Jarvis, un asistente personal amable y claro. Responde siempre en español."


def preguntar(
    pregunta: str,
    historial: list[dict[str, str]] | None = None,
    contexto: list[str] | None = None,
) -> str:
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        raise ValueError("Falta GEMINI_API_KEY en el archivo .env")

    contenidos: list[Any] = []
    if historial:
        contenidos.extend(
            types.Content(
                role="model" if mensaje["role"] == "assistant" else "user",
                parts=[types.Part.from_text(text=mensaje["content"])],
            )
            for mensaje in historial
        )
    contenidos.append(pregunta)

    instruccion = INSTRUCCION
    if contexto:
        recuerdos = "\n".join(f"- {recuerdo}" for recuerdo in contexto)
        instruccion += (
            "\nUsa estos recuerdos guardados localmente solo si son relevantes. "
            "No inventes otros recuerdos ni los presentes como información recién verificada:\n"
            f"{recuerdos}"
        )

    cliente = genai.Client(api_key=clave)
    respuesta = cliente.models.generate_content(
        model=MODELO,
        contents=contenidos,
        config=types.GenerateContentConfig(system_instruction=instruccion),
    )
    if respuesta.text is None:
        raise RuntimeError("Gemini no devolvió texto.")
    return respuesta.text