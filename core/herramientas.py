from core import internet, utilidades

def manejar(texto: str):
    for modulo in (utilidades, internet):
        respuesta = modulo.manejar(texto)
        if respuesta:
            return respuesta
    return None