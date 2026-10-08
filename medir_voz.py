import sounddevice as sd

from voz.mi_voz import FRECUENCIA, UMBRAL_VOZ, parecido

input("Presiona Enter y di una frase durante 5 segundos...")
grabacion = sd.rec(
    int(5 * FRECUENCIA), samplerate=FRECUENCIA, channels=1, dtype="float32"
)
sd.wait()
valor = parecido(grabacion.flatten())
print(f"Parecido con tu voz: {valor:.2f} (umbral actual: {UMBRAL_VOZ})")
print("SE ACEPTA" if valor >= UMBRAL_VOZ else "SE RECHAZA")
