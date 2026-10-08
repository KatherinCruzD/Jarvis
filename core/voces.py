import re
import unicodedata

from voz import hablar


def _simple(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _estado() -> str:
    actual = hablar.motor_preferido()
    partes = [f"Ahora hablo con la {hablar.NOMBRES[actual]}."]
    if actual != "windows" and not hablar.piper_disponible():
        partes.append("La voz local todavía no está descargada.")
    partes.append(
        "Puedo usar tres voces: la de Windows, la local y la de internet. "
        "Dime, por ejemplo, «cambia la voz a la de internet»."
    )
    return " ".join(partes)


def manejar(texto: str):
    t = _simple(texto).strip(" ¿?¡!.,")
    if "voz" not in t and "hablar" not in t:
        return None

    if re.search(r"(que|cual) voz (estas usando|tienes|uso)|que voces (tienes|hay)|lista de voces", t):
        return _estado()

    if not re.search(r"\b(cambia|cambiar|usa|usar|pon|poner|activa|activar|elige|quiero|habla|hablar)\b", t):
        return None

    if re.search(r"autom", t):
        motor = "auto"
    elif re.search(r"internet|natural|online|en linea|edge|nube", t):
        motor = "edge"
    elif re.search(r"local|neuronal|piper|sin internet|offline", t):
        motor = "piper"
    elif re.search(r"windows|normal|clasica|predeterminada|de siempre|robot", t):
        motor = "windows"
    else:
        return None

    if motor == "piper" and not hablar.piper_disponible():
        return (
            "No puedo usar la voz local porque aún no está descargada. "
            "Descárgala una vez con internet y vuelve a pedírmelo."
        )
    hablar.elegir_motor(motor)
    return f"Listo, ahora hablo con la {hablar.NOMBRES[motor]}."