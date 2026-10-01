import subprocess
import threading
import time

import uvicorn

DIRECCION = "http://127.0.0.1:8000"

def abrir_ventana():
    time.sleep(2)
    subprocess.Popen(
        ["cmd", "/c", "start", "", "msedge", f"--app={DIRECCION}"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

def main():
    threading.Thread(target=abrir_ventana, daemon=True).start()
    uvicorn.run("servidor.app:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()