import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODELO = "gemini-3.8-flash"
INSTRUCCION = "Eres Jarvis, un asistente personal amable y claro. Responde siempre en español."

def preguntar(pregunta: str) -> str:
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        raise ValueError("Falta GEMINI_API_KEY en el archivo .env")

    cliente = genai.Client(api_key=clave)
    respuesta = cliente.models.generate_content(
        model=MODELO,
        contents=pregunta,
        config=types.GenerateContentConfig(system_instruction=INSTRUCCION),
    )
    return respuesta.text