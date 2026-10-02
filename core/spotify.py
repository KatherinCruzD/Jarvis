import base64
import hashlib
import http.server
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from core.acciones import abrir_busqueda_spotify, ejecutar_atajo
from dotenv import load_dotenv

load_dotenv()

SCOPE = "user-read-playback-state user-modify-playback-state"
REDIRECT_URI = "http://127.0.0.1:8765/callback"


def _token_path() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / "Jarvis" / "spotify_token.json"


def _client_id() -> str:
    client_id = os.environ.get("JARVIS_SPOTIFY_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError(
            "Falta JARVIS_SPOTIFY_CLIENT_ID. Registra una aplicación de Spotify "
            "y configura su Client ID y la URI http://127.0.0.1:8765/callback."
        )
    return client_id


def _post_form(url: str, datos: dict[str, str]) -> dict:
    peticion = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(datos).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Spotify OAuth respondió HTTP {error.code}: {detalle[:400]}"
        ) from error


def _autorizar(client_id: str) -> dict:
    estado = secrets.token_urlsafe(32)
    verificador = secrets.token_urlsafe(64)
    desafio = base64.urlsafe_b64encode(
        hashlib.sha256(verificador.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    recibido: dict[str, str] = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parametros = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            )
            recibido["state"] = parametros.get("state", [""])[0]
            recibido["code"] = parametros.get("code", [""])[0]
            recibido["error"] = parametros.get("error", [""])[0]
            contenido = (
                b"Autorizacion recibida. Puedes cerrar esta ventana y volver a Jarvis."
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)

        def log_message(self, _format, *_args):
            return

    servidor = http.server.HTTPServer(("127.0.0.1", 8765), Callback)
    servidor.timeout = 240
    parametros = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": estado,
        "code_challenge_method": "S256",
        "code_challenge": desafio,
    }
    url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode(parametros)
    )
    try:
        if not webbrowser.open(url, new=2):
            raise RuntimeError("No se pudo abrir el navegador para autorizar Spotify.")
        servidor.handle_request()
    finally:
        servidor.server_close()

    if recibido.get("state") != estado:
        raise PermissionError("La respuesta OAuth de Spotify no coincide con la solicitud.")
    if recibido.get("error"):
        raise PermissionError(f"Autorización de Spotify cancelada: {recibido['error']}.")
    if not recibido.get("code"):
        raise TimeoutError("No llegó la autorización de Spotify en cuatro minutos.")

    token = _post_form(
        "https://accounts.spotify.com/api/token",
        {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": recibido["code"],
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verificador,
        },
    )
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    _guardar_token(token)
    return token


def _guardar_token(token: dict) -> None:
    ruta = _token_path()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(token), encoding="utf-8")
    os.replace(temporal, ruta)


def _access_token() -> str:
    client_id = _client_id()
    ruta = _token_path()
    try:
        token = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        token = _autorizar(client_id)

    if float(token.get("expires_at", 0)) <= time.time() + 60:
        refresh = token.get("refresh_token")
        if not refresh:
            token = _autorizar(client_id)
        else:
            renovado = _post_form(
                "https://accounts.spotify.com/api/token",
                {
                    "client_id": client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
            )
            token.update(renovado)
            token["expires_at"] = time.time() + int(
                renovado.get("expires_in", 3600)
            )
            _guardar_token(token)
    return token["access_token"]


def _spotify(
    metodo: str,
    ruta: str,
    cuerpo: dict | None = None,
) -> dict:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        f"https://api.spotify.com/v1/{ruta}",
        data=datos,
        headers={
            "Authorization": f"Bearer {_access_token()}",
            "Content-Type": "application/json",
        },
        method=metodo,
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            contenido = respuesta.read()
            return json.loads(contenido) if contenido else {}
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        if error.code == 403:
            raise RuntimeError(
                "Spotify no autorizó la reproducción. Se requiere Spotify Premium "
                "y un dispositivo de reproducción activo."
            ) from error
        if error.code == 404:
            raise RuntimeError(
                "No encontré la canción o no hay un dispositivo Spotify activo."
            ) from error
        raise RuntimeError(
            f"Spotify respondió HTTP {error.code}: {detalle[:400]}"
        ) from error


def _reproducir_con_api(consulta: str) -> str:
    parametros = urllib.parse.urlencode(
        {"q": consulta, "type": "track", "limit": "1"}
    )
    resultado = _spotify("GET", f"search?{parametros}")
    pistas = resultado.get("tracks", {}).get("items", [])
    if not pistas:
        return f"No encontré {consulta} en Spotify."

    dispositivos = _spotify("GET", "me/player/devices").get("devices", [])
    if not dispositivos:
        ejecutar_atajo("spotify")
        for _ in range(8):
            time.sleep(1)
            dispositivos = _spotify("GET", "me/player/devices").get("devices", [])
            if dispositivos:
                break
    if not dispositivos:
        raise RuntimeError(
            "Abrí Spotify, pero no aparece ningún dispositivo disponible. "
            "Inicia sesión en la aplicación e inténtalo de nuevo."
        )
    dispositivo = next(
        (dispositivo for dispositivo in dispositivos if dispositivo.get("is_active")),
        dispositivos[0],
    )
    pista = pistas[0]
    ruta = "me/player/play?" + urllib.parse.urlencode(
        {"device_id": dispositivo["id"]}
    )
    _spotify("PUT", ruta, {"uris": [pista["uri"]]})
    artistas = ", ".join(
        artista["name"] for artista in pista.get("artists", [])
    )
    return f"Reproduciendo {pista['name']} de {artistas} en Spotify."


def _buscar_para_reproduccion_manual(consulta: str) -> str:
    abrir_busqueda_spotify(consulta)
    return (
        f"Abrí la búsqueda de {consulta} en Spotify. Con una cuenta gratis, "
        "elige allí la canción para reproducirla; la API oficial no permite "
        "que Jarvis inicie la reproducción automáticamente sin Premium."
    )


def reproducir_cancion(consulta: str) -> str:
    consulta = consulta.strip()
    if not consulta or len(consulta) > 180:
        raise ValueError("Indica una canción con un nombre de hasta 180 caracteres.")

    if not os.environ.get("JARVIS_SPOTIFY_CLIENT_ID", "").strip():
        return _buscar_para_reproduccion_manual(consulta)

    try:
        return _reproducir_con_api(consulta)
    except RuntimeError as error:
        if "Se requiere Spotify Premium" in str(error):
            return _buscar_para_reproduccion_manual(consulta)
        raise
