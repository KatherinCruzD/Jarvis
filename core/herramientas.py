from core import internet, utilidades, voces
from core.pantalla import consultas as pantalla


def manejar(texto: str):
    for modulo in (voces, utilidades, pantalla, internet):
        respuesta = modulo.manejar(texto)
        if respuesta:
            return respuesta
    return None