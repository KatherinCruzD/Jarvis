import ctypes
import os
import threading
from collections.abc import Callable

TECLA_F8 = 0x77
TECLA_PRESIONADA = 0x8000


def _crear_lector_f8() -> Callable[[], bool]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_async_key_state = user32.GetAsyncKeyState
    get_async_key_state.argtypes = [ctypes.c_int]
    get_async_key_state.restype = ctypes.c_short

    def f8_presionada() -> bool:
        return bool(get_async_key_state(TECLA_F8) & TECLA_PRESIONADA)

    return f8_presionada


def vigilar_f8(
    detener: threading.Event,
    hablando: threading.Event,
    interrumpir: threading.Event,
    leer_tecla: Callable[[], bool] | None = None,
) -> None:
    if leer_tecla is None:
        if os.name != "nt":
            return
        leer_tecla = _crear_lector_f8()

    estaba_presionada = False
    while not detener.wait(0.02):
        presionada = leer_tecla()
        if presionada and not estaba_presionada and hablando.is_set():
            interrumpir.set()
        estaba_presionada = presionada
