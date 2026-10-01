from core.asistente import PROVEEDORES, responder

def main():
    proveedor = "local"
    print("Jarvis iniciado. Comandos: /local, /gemini, salir")
    while True:
        texto = input("Tú: ").strip()
        if not texto:
            continue
        if texto.lower() == "salir":
            print("Jarvis: ¡Hasta luego!")
            break
        if texto.startswith("/") and texto[1:] in PROVEEDORES:
            proveedor = texto[1:]
            print(f"Jarvis: Listo, ahora uso la IA '{proveedor}'.")
            continue
        print(f"Jarvis ({proveedor}): {responder(texto, proveedor)}")

if __name__ == "__main__":
    main()