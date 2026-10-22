import argparse
import time

from core.pantalla.captura import capturar
from core.pantalla.ocr import MINIMO_CARACTERES, leer

lector = argparse.ArgumentParser(description="Prueba el OCR de Windows sobre tu pantalla.")
lector.add_argument("--ventana", action="store_true", help="lee solo la ventana de arriba")
lector.add_argument("--espera", type=int, default=5, help="segundos antes de capturar")
argumentos = lector.parse_args()

for segundos in range(argumentos.espera, 0, -1):
    print(f"Capturando en {segundos}... pon al frente lo que quieres que lea")
    time.sleep(1)

imagen, donde = capturar("ventana" if argumentos.ventana else "pantalla")
print(f"Captura lista: {donde}")

inicio = time.time()
texto, idioma = leer(imagen)
print(f"OCR terminó en {time.time() - inicio:.1f} s")

if not idioma:
    print("\nNo pude usar el OCR de Windows. Abre PowerShell COMO ADMINISTRADORA y escribe:")
    print('Add-WindowsCapability -Online -Name "Language.OCR~~~es-ES~0.0.1.0"')
else:
    print(f"Idioma de OCR usado: {idioma} | caracteres leídos: {len(texto)}")
    print("Alcanza para responder con el modelo de texto." if len(texto) >= MINIMO_CARACTERES
          else "Poco texto: Jarvis usaría el modelo de visión.")
    print("\n----- TEXTO LEÍDO -----")
    print(texto[:1500])