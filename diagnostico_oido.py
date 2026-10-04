import os

import numpy as np
import sounddevice as sd

from voz import mi_voz, oido

SEGUNDOS = 6
PRUEBAS = 3

micro = oido._dispositivo_microfono()
print("Micrófono:", sd.query_devices(micro, kind="input")["name"])
estado = "activa" if mi_voz.verificacion_activa() else "APAGADA (solo para pruebas)"
print(f"Verificación de voz: {estado} | umbral: {mi_voz.UMBRAL_VOZ:.2f}")
if mi_voz.cargar_huella() is None:
    raise SystemExit("No hay huella de voz. Ejecuta primero: python registrar_voz.py")

for n in range(1, PRUEBAS + 1):
    input(f"\nPrueba {n}/{PRUEBAS}: presiona Enter y di 'Jarvis, abre Word' (tienes {SEGUNDOS} s)...")
    grabacion = sd.rec(
        int(SEGUNDOS * mi_voz.FRECUENCIA),
        samplerate=mi_voz.FRECUENCIA,
        channels=1,
        dtype="float32",
        device=micro,
    )
    sd.wait()
    audio = grabacion.flatten()

    maximo = float(np.abs(audio).max())
    print(f"1) Volumen máximo: {maximo:.2f}", "-> bien" if maximo >= 0.03 else "-> MUY BAJO: sube el volumen del micrófono en Windows o acércate")
    if maximo < 0.03:
        continue

    valor = mi_voz.parecido(audio)
    pasa = valor >= mi_voz.UMBRAL_VOZ
    print(f"2) Parecido con tu voz: {valor:.2f} (necesito {mi_voz.UMBRAL_VOZ:.2f})", "-> te acepta" if pasa else "-> TE RECHAZA")

    normalizado = (audio / maximo * 0.9).astype(np.float32)
    texto = oido.transcribir(normalizado)
    print(f"3) Whisper entendió: {texto!r}")
    comando = oido.quitar_activacion(texto)
    if comando is None:
        print("4) Palabra Jarvis: NO la detectó al inicio de la frase")
    else:
        print(f"4) Palabra Jarvis: detectada. Orden que recibiría: {comando!r}")

    if pasa and comando:
        print("RESULTADO: todo bien en esta prueba.")
    elif not pasa:
        print("RESULTADO: falla el candado de voz. Vuelve a ejecutar registrar_voz.py.")
    else:
        print("RESULTADO: falla el reconocimiento de la palabra Jarvis. Mándame lo que entendió Whisper.")