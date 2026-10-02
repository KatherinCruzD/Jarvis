import base64
import hashlib
import http.server
import json
import mimetypes
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from core.archivos import raices_archivos_personales
from dotenv import load_dotenv

load_dotenv()

SCOPE = "https://www.googleapis.com/auth/drive.file"
MAXIMO_SUBIDA = 50 * 1024 * 1024
CLIENTE_OAUTH = Path(__file__).resolve().parent.parent / "secrets" / "google_oauth_client.json"


def _token_path() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / "Jarvis" / "google_drive_token.json"


def _leer_cliente() -> dict[str, str]:
    ruta = Path(os.environ.get("JARVIS_GOOGLE_OAUTH_CLIENT", CLIENTE_OAUTH))
    if not ruta.is_file():
        raise FileNotFoundError(
            "Falta el cliente OAuth de Google. Guarda el JSON de aplicación de escritorio "
            f"en {ruta} y habilita Google Drive API."
        )
    with ruta.open(encoding="utf-8") as archivo:
        configuracion = json.load(archivo)
    cliente = configuracion.get("installed")
    if not isinstance(cliente, dict):
        raise ValueError("El JSON OAuth debe ser una credencial de aplicación de escritorio.")
    return cliente


def _guardar_token(token: dict) -> None:
    ruta = _token_path()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(token), encoding="utf-8")
    os.replace(temporal, ruta)


def _solicitud_json(url: str, datos: dict[str, str]) -> dict:
    cuerpo = urllib.parse.urlencode(datos).encode("ascii")
    peticion = urllib.request.Request(
        url,
        data=cuerpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Google OAuth respondió HTTP {error.code}: {detalle[:500]}"
        ) from error


def _autorizar(cliente: dict[str, str]) -> dict:
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

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Callback)
    servidor.timeout = 240
    redirect_uri = f"http://127.0.0.1:{servidor.server_port}/"
    parametros = {
        "client_id": cliente["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": estado,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
    }
    url = f'{cliente["auth_uri"]}?{urllib.parse.urlencode(parametros)}'
    import webbrowser

    try:
        if not webbrowser.open(url, new=2):
            raise RuntimeError("No se pudo abrir el navegador para autorizar Google.")
        servidor.handle_request()
    finally:
        servidor.server_close()

    if recibido.get("state") != estado:
        raise PermissionError("La respuesta OAuth de Google no coincide con la solicitud.")
    if recibido.get("error"):
        raise PermissionError(f"Autorización de Google cancelada: {recibido['error']}.")
    if not recibido.get("code"):
        raise TimeoutError("No llegó la autorización de Google dentro de cuatro minutos.")

    token = _solicitud_json(
        cliente["token_uri"],
        {
            "client_id": cliente["client_id"],
            "client_secret": cliente.get("client_secret", ""),
            "code": recibido["code"],
            "code_verifier": verificador,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    token["token_uri"] = cliente["token_uri"]
    token["client_id"] = cliente["client_id"]
    token["client_secret"] = cliente.get("client_secret", "")
    _guardar_token(token)
    return token


def _access_token() -> str:
    cliente = _leer_cliente()
    ruta = _token_path()
    try:
        token = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        token = _autorizar(cliente)

    if float(token.get("expires_at", 0)) <= time.time() + 60:
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            token = _autorizar(cliente)
        else:
            renovado = _solicitud_json(
                cliente["token_uri"],
                {
                    "client_id": cliente["client_id"],
                    "client_secret": cliente.get("client_secret", ""),
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token.update(renovado)
            token["expires_at"] = time.time() + int(
                renovado.get("expires_in", 3600)
            )
            _guardar_token(token)
    return token["access_token"]


def _solicitud_drive(
    metodo: str,
    endpoint: str,
    cuerpo: bytes | None = None,
    content_type: str = "application/json",
) -> dict:
    peticion = urllib.request.Request(
        endpoint,
        data=cuerpo,
        headers={
            "Authorization": f"Bearer {_access_token()}",
            "Content-Type": content_type,
        },
        method=metodo,
    )
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            return json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Google Drive respondió HTTP {error.code}: {detalle[:500]}"
        ) from error


def crear_carpeta(nombre: str) -> str:
    nombre = nombre.strip()
    if not nombre or len(nombre) > 120:
        raise ValueError("El nombre de carpeta debe tener entre 1 y 120 caracteres.")
    resultado = _solicitud_drive(
        "POST",
        "https://www.googleapis.com/drive/v3/files?fields=id%2Cname%2CwebViewLink",
        json.dumps(
            {"name": nombre, "mimeType": "application/vnd.google-apps.folder"}
        ).encode("utf-8"),
    )
    return f"Creé la carpeta {resultado.get('name', nombre)} en Google Drive."


def subir_archivo(ruta: Path) -> str:
    ruta = Path(ruta).resolve(strict=True)
    raices = [raiz.resolve() for raiz in raices_archivos_personales()]
    if not any(ruta.is_relative_to(raiz) for raiz in raices):
        raise PermissionError("Solo puedo subir archivos de Escritorio, Documentos o Descargas.")
    if not ruta.is_file():
        raise ValueError("La ruta seleccionada no es un archivo.")
    if ruta.stat().st_size > MAXIMO_SUBIDA:
        raise ValueError("Por seguridad, la subida está limitada a archivos de 50 MB.")

    limite = f"jarvis-{secrets.token_hex(16)}"
    metadata = json.dumps({"name": ruta.name}).encode("utf-8")
    mime_type = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
    contenido = ruta.read_bytes()
    cuerpo = (
        b"--" + limite.encode("ascii") + b"\r\n"
        b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        + metadata
        + b"\r\n--"
        + limite.encode("ascii")
        + b"\r\nContent-Type: "
        + mime_type.encode("ascii")
        + b"\r\n\r\n"
        + contenido
        + b"\r\n--"
        + limite.encode("ascii")
        + b"--\r\n"
    )
    url = (
        "https://www.googleapis.com/upload/drive/v3/files"
        "?uploadType=multipart&fields=id%2Cname%2CwebViewLink"
    )
    resultado = _solicitud_drive(
        "POST",
        url,
        cuerpo,
        f"multipart/related; boundary={limite}",
    )
    return f"Subí {resultado.get('name', ruta.name)} a Google Drive."
