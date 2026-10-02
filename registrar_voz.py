import sounddevice as sd

from voz.mi_voz import FRECUENCIA, guardar_huella, huella

SEGUNDOS = 25
TEXTO = (
    "Hola, soy yo y estoy configurando mi asistente Jarvis. "
    "Quiero que reconozca mi voz y que solo me obedezca a mí. "
    "Hoy es un buen día para construir algo increíble, así que vamos a empezar. "
    "Me gusta aprender programación y crear proyectos para mi portafolio."
)

print("Lee en voz alta, con tu tono normal y sin apuro (puedes repetirlo):\n")
print(TEXTO)
input("\nPresiona Enter y empieza a leer...")
grabacion = sd.rec(
    int(SEGUNDOS * FRECUENCIA), samplerate=FRECUENCIA, channels=1, dtype="float32"
)
sd.wait()
resultado = huella(grabacion.flatten())
if resultado is None:
    print("Se escuchó muy poca voz. Intenta de nuevo, más cerca del micrófono.")
else:
    guardar_huella(resultado)
    print("Listo: tu voz quedó registrada.")