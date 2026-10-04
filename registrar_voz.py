import numpy as np
import sounddevice as sd

from voz import mi_voz

FRASES = [
    "Jarvis, abre Word.",
    "Jarvis, ¿qué hora es?",
    "Jarvis, busca el archivo informe.",
    "Jarvis, pon música en YouTube.",
    "Jarvis, apunta una nota para mañana.",
    "Jarvis, detente.",
    "Jarvis, ¿cómo está el clima hoy?",
    "Jarvis, crea una carpeta en Drive.",
]
SEGUNDOS = 5


def dispositivo():
    try:
        from voz.oido import _dispositivo_microfono

        return _dispositivo_microfono()
    except Exception as error:
        print("Aviso: usaré el micrófono predeterminado de Windows:", error)
        return None


def grabar(micro):
    grabacion = sd.rec(
        int(SEGUNDOS * mi_voz.FRECUENCIA),
        samplerate=mi_voz.FRECUENCIA,
        channels=1,
        dtype="float32",
        device=micro,
    )
    sd.wait()
    return grabacion.flatten()


micro = dispositivo()
print("Micrófono:", sd.query_devices(micro, kind="input")["name"])
print("\nVas a decir 8 frases cortas, cada una con TU voz normal, a unos 30 cm del")
print("computador y en un lugar silencioso. Habla como le hablarías a Jarvis.\n")

huellas = []
for numero, frase in enumerate(FRASES, 1):
    for intento in range(2):
        input(f"[{numero}/{len(FRASES)}] Presiona Enter y di: {frase}")
        audio = grabar(micro)
        maximo = float(np.abs(audio).max())
        if maximo < 0.05:
            print(f"   Se oyó muy bajito (volumen {maximo:.2f}). Intenta de nuevo, más cerca.")
            continue
        valor = mi_voz.huella(audio)
        if valor is None:
            print("   No se detectó suficiente voz. Intenta de nuevo.")
            continue
        huellas.append(valor)
        print(f"   Muestra guardada (volumen {maximo:.2f}).")
        break

if len(huellas) < 6:
    print(f"\nSolo salieron {len(huellas)} muestras buenas de 8. Repite en un lugar más")
    print("silencioso y más cerca del micrófono. No se guardó nada nuevo.")
else:
    resumen = mi_voz.guardar_perfil(huellas)
    print("\nListo: tu voz quedó registrada con", len(huellas), "muestras.")
    print(f"Parecido entre tus propias muestras: mínimo {resumen['minima']:.2f}, promedio {resumen['media']:.2f}")
    print(f"Umbral que usará Jarvis: {resumen['umbral']:.2f}")
    if resumen["minima"] < 0.65:
        print("Tu voz cambió mucho entre muestras o había ruido: conviene repetir el registro.")
        