import os
import re
import urllib.parse
import webbrowser
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

load_dotenv()
CIUDAD = os.getenv("JARVIS_CIUDAD", "Ibagué")
CABECERAS = {"User-Agent": "JarvisAsistente/1.0 (proyecto personal de aprendizaje)"}

CODIGOS_CLIMA = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado",
    3: "nublado", 45: "con niebla", 48: "con niebla", 51: "con llovizna",
    53: "con llovizna", 55: "con llovizna", 61: "con lluvia", 63: "con lluvia",
    65: "con lluvia fuerte", 80: "con aguaceros", 81: "con aguaceros",
    82: "con aguaceros fuertes", 95: "con tormenta eléctrica",
    96: "con tormenta", 99: "con tormenta",
}

MONEDAS = {"dólar": "USD", "dolar": "USD", "euro": "EUR", "libra": "GBP", "yen": "JPY"}


def consultar_clima(ciudad: str = CIUDAD) -> str:
    try:
        lugar = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ciudad, "count": 1, "language": "es"},
            headers=CABECERAS,
            timeout=8,
        ).json()
        if not lugar.get("results"):
            return f"No encontré la ciudad {ciudad}."
        sitio = lugar["results"][0]
        datos = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": sitio["latitude"],
                "longitude": sitio["longitude"],
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 1,
            },
            headers=CABECERAS,
            timeout=8,
        ).json()
        actual = datos["current"]
        maxima = datos["daily"]["temperature_2m_max"][0]
        minima = datos["daily"]["temperature_2m_min"][0]
    except Exception:
        return "No pude consultar el clima, revisa tu conexión a internet."

    estado = CODIGOS_CLIMA.get(actual["weather_code"], "variable")
    return (
        f"En {sitio['name']} hay {actual['temperature_2m']:.0f} grados, {estado}. "
        f"Hoy la máxima es de {maxima:.0f} y la mínima de {minima:.0f}."
    )


def consultar_wikipedia(tema: str) -> str:
    try:
        busqueda = requests.get(
            "https://es.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": tema, "limit": 1, "format": "json"},
            headers=CABECERAS,
            timeout=8,
        ).json()
        if not busqueda[1]:
            return f"No encontré nada sobre {tema} en Wikipedia."
        titulo = busqueda[1][0].replace(" ", "_")
        resumen = requests.get(
            "https://es.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(titulo),
            headers=CABECERAS,
            timeout=8,
        ).json()
        texto = resumen.get("extract", "")
    except Exception:
        return "No pude consultar Wikipedia, revisa tu conexión a internet."

    if not texto:
        return f"No encontré un resumen de {tema}."
    frases = re.split(r"(?<=[.!?])\s+", texto)
    corto = " ".join(frases[:2])
    return corto if len(corto) <= 450 else frases[0]


def cotizar(nombre: str) -> str:
    codigo = MONEDAS[nombre]
    try:
        tasas = requests.get(
            "https://open.er-api.com/v6/latest/USD", headers=CABECERAS, timeout=8
        ).json()["rates"]
        valor = tasas["COP"] / tasas[codigo]
    except Exception:
        return "No pude consultar las divisas, revisa tu conexión a internet."

    formato = f"{valor:,.2f}" if valor < 100 else f"{valor:,.0f}"
    formato = formato.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Un {nombre} equivale a unos {formato} pesos colombianos."


def noticias() -> str:
    try:
        respuesta = requests.get(
            "https://feeds.bbci.co.uk/mundo/rss.xml", headers=CABECERAS, timeout=8
        )
        raiz = ET.fromstring(respuesta.content)
        titulos = [i.findtext("title") for i in raiz.iter("item")][:5]
    except Exception:
        return "No pude consultar las noticias, revisa tu conexión a internet."

    titulos = [t for t in titulos if t]
    if not titulos:
        return "No encontré noticias en este momento."
    return "Estos son los titulares: " + "; ".join(titulos) + "."


def buscar_en_google(consulta: str) -> str:
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(consulta))
    return f"Buscando {consulta} en Google."


def manejar(texto: str):
    limpio = re.sub(r"\b(hoy|ahora|por favor)\b", "", texto.lower())
    t = limpio.strip(" ¿?¡!.,")

    if re.search(r"clima|va a llover|qué tiempo hace", t):
        ciudad = re.search(r"\ben ([a-záéíóúñ ]+)$", t)
        return consultar_clima(ciudad.group(1).strip() if ciudad else CIUDAD)

    if re.search(r"noticias|titulares", t):
        return noticias()

    moneda = re.search(
        r"(?:cotizaci[oó]n|precio|cu[aá]nto (?:est[aá]|vale|cuesta)) "
        r"(?:del |de la |el |la )?(d[oó]lar|euro|libra|yen)",
        t,
    )
    if moneda:
        return cotizar(moneda.group(1))

    wiki = re.search(
        r"(?:busca|consulta|investiga)(?: en)? wikipedia (?:sobre |acerca de |de )?(.+)", t
    ) or re.search(r"(?:busca|dime|qué es|quién es|quién fue) (.+) en wikipedia", t)
    if wiki:
        return consultar_wikipedia(wiki.group(1).strip())

    google = re.search(r"busca en google (.+)", t) or re.search(r"busca (.+) en google", t)
    if google:
        return buscar_en_google(google.group(1).strip())

    return None