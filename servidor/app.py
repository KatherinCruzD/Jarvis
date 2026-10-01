import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.acciones import ejecutar_atajo
from core.asistente import responder
from voz.hablar import hablar

CARPETA_WEB = Path(__file__).resolve().parent.parent / "web"

app = FastAPI()
app.mount("/static", StaticFiles(directory=CARPETA_WEB), name="static")


@app.get("/")
def inicio():
    return FileResponse(CARPETA_WEB / "index.html")


async def enviar(ws: WebSocket, **datos):
    await ws.send_text(json.dumps(datos))


@app.websocket("/ws")
async def conexion(ws: WebSocket):
    await ws.accept()
    voz_activa = True
    proveedor = "local"
    try:
        while True:
            mensaje = json.loads(await ws.receive_text())
            tipo = mensaje.get("tipo")

            if tipo == "voz":
                voz_activa = bool(mensaje["valor"])
            elif tipo == "proveedor":
                proveedor = mensaje["valor"]
            elif tipo == "atajo":
                texto = ejecutar_atajo(mensaje["valor"])
                await enviar(ws, tipo="respuesta", texto=texto)
            elif tipo == "texto":
                await enviar(ws, tipo="estado", valor="pensando")
                respuesta = await asyncio.to_thread(
                    responder, mensaje["texto"], proveedor
                )
                await enviar(ws, tipo="respuesta", texto=respuesta)
                if voz_activa:
                    await enviar(ws, tipo="estado", valor="hablando")
                    await asyncio.to_thread(hablar, respuesta)
                await enviar(ws, tipo="estado", valor="reposo")
    except WebSocketDisconnect:
        pass