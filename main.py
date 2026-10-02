import asyncio
import subprocess

import uvicorn

from servidor.app import app

DIRECCION = "http://127.0.0.1:8000"


async def main():
    servidor = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8000)
    )
    app.state.servidor_uvicorn = servidor

    async def abrir_ventana():
        await asyncio.sleep(2)
        if not servidor.should_exit:
            await asyncio.to_thread(
                subprocess.Popen,
                ["cmd", "/c", "start", "", "msedge", f"--app={DIRECCION}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

    tarea_ventana = asyncio.create_task(abrir_ventana())
    try:
        await servidor.serve()
    finally:
        tarea_ventana.cancel()
        await asyncio.gather(tarea_ventana, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())