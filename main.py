from ai.ollama_client import preguntar

def main():
    print("Jarvis iniciado. Escribe 'salir' para terminar.")
    while True:
        texto = input("Tú: ")
        if texto.lower() == "salir":
            print("Jarvis: ¡Hasta luego!")
            break
        respuesta = preguntar(texto)
        print(f"Jarvis: {respuesta}")

if __name__ == "__main__":
    main()