from core import internet, utilidades, voces


def manejar(texto: str):
    for modulo in (voces, utilidades, internet):
        respuesta = modulo.manejar(texto)
        if respuesta:
            return respuesta
    return None