import ollama

MODELO = "llama3.2:3b"
INSTRUCCION = "Eres Jarvis, un asistente personal amable y claro. Responde siempre en español."

def preguntar(pregunta: str) -> str:
    respuesta = ollama.chat(
        model=MODELO,
        messages=[
            {"role": "system", "content": INSTRUCCION},
            {"role": "user", "content": pregunta},
        ],
    )
    return respuesta["message"]["content"]