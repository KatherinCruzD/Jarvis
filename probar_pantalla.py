import argparse
import os
import time
from pathlib import Path

from core.pantalla import vision
from core.pantalla.captura import capturar

lector = argparse.ArgumentParser(description="Prueba la conciencia de pantalla de Jarvis.")
lector.add_argument(
    "pregunta",
    nargs="?",
    default="Describe qué se ve en mi pantalla y en qué estoy trabajando.",
    help="lo que quieres preguntarle a Jarvis sobre la pantalla",
)
lector.add_argument("--ventana", action="store_true", help="captura solo la ventana de arriba")
lector.add_argument("--espera", type=int, default=5, help="segundos antes de capturar")
lector.add_argument("--guardar", action="store_true", help="guarda la captura para que veas qué recibió la IA")
argumentos = lector.parse_args()

proveedor = vision.proveedor_de_vision()
modelo = vision.MODELO_LOCAL if proveedor == "local" else "Gemini (nube)"
print(f"Analizará: {modelo} | proveedor: {proveedor}")
if proveedor == "gemini":
    print("AVISO: la imagen de tu pantalla se enviará a Google. Cierra lo privado.")

for segundos in range(argumentos.espera, 0, -1):
    print(f"Capturando en {segundos}... pon al frente lo que quieres que vea")
    time.sleep(1)

imagen, donde = capturar("ventana" if argumentos.ventana else "pantalla")
print(f"Captura lista: {donde} ({len(imagen) / 1024:.0f} KB)")

if argumentos.guardar:
    carpeta = Path.home() / "Pictures" / "Capturas Jarvis"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "ultima_prueba_vision.png"
    ruta.write_bytes(imagen)
    print(f"Guardada en: {ruta}")

print("Pensando (con el procesador puede tardar de 20 a 90 segundos)...")
inicio = time.time()
respuesta = vision.analizar(imagen, argumentos.pregunta)
print(f"\nJarvis ({time.time() - inicio:.0f} s): {respuesta}")