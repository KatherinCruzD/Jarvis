import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from resemblyzer import VoiceEncoder, preprocess_wav

load_dotenv()

FRECUENCIA = 16000
CARPETA = Path(__file__).resolve().parent
ARCHIVO = CARPETA / "mi_voz.npy"
ARCHIVO_UMBRAL = CARPETA / "mi_voz_umbral.json"
UMBRAL_PREDETERMINADO = 0.70

_codificador = None


def _leer_umbral() -> float:
    manual = os.getenv("JARVIS_UMBRAL_VOZ", "").strip()
    if manual:
        try:
            return min(0.95, max(0.30, float(manual.replace(",", "."))))
        except ValueError:
            pass
    try:
        datos = json.loads(ARCHIVO_UMBRAL.read_text(encoding="utf-8"))
        return float(datos["umbral"])
    except (OSError, ValueError, KeyError, TypeError):
        return UMBRAL_PREDETERMINADO


UMBRAL_VOZ = _leer_umbral()


def _encoder():
    global _codificador
    if _codificador is None:
        _codificador = VoiceEncoder()
    return _codificador


def huella(audio):
    wav = preprocess_wav(audio, source_sr=FRECUENCIA)
    if len(wav) < FRECUENCIA:
        return None
    return _encoder().embed_utterance(wav)


def guardar_huella(valor):
    np.save(ARCHIVO, valor)


def _unitario(vector):
    return vector / np.linalg.norm(vector)


def guardar_perfil(huellas: list) -> dict:
    """Guarda el promedio de varias muestras y calcula un umbral a partir de ellas."""
    if len(huellas) < 3:
        raise ValueError("Se necesitan al menos 3 muestras válidas.")
    muestras = [_unitario(np.asarray(h, dtype=np.float64)) for h in huellas]
    media = _unitario(np.mean(muestras, axis=0))
    propias = []
    for i, muestra in enumerate(muestras):
        resto = _unitario(np.mean([m for j, m in enumerate(muestras) if j != i], axis=0))
        propias.append(float(np.dot(resto, muestra)))
    umbral = round(min(0.80, max(0.60, min(propias) - 0.05)), 2)
    np.save(ARCHIVO, media)
    ARCHIVO_UMBRAL.write_text(
        json.dumps({"umbral": umbral, "similitudes": propias}, indent=2),
        encoding="utf-8",
    )
    global UMBRAL_VOZ
    UMBRAL_VOZ = _leer_umbral()
    return {"umbral": UMBRAL_VOZ, "minima": min(propias), "media": float(np.mean(propias))}


def cargar_huella():
    return np.load(ARCHIVO) if ARCHIVO.exists() else None


def verificacion_activa() -> bool:
    return os.getenv("JARVIS_VERIFICAR_VOZ", "1").strip() != "0"


def parecido(audio) -> float:
    if not verificacion_activa():
        return 1.0
    referencia = cargar_huella()
    actual = huella(audio)
    if referencia is None or actual is None:
        return 0.0

    norma_referencia = float(np.linalg.norm(referencia))
    norma_actual = float(np.linalg.norm(actual))
    if (
        not np.isfinite(norma_referencia)
        or not np.isfinite(norma_actual)
        or norma_referencia == 0
        or norma_actual == 0
    ):
        return 0.0

    similitud = float(np.dot(referencia, actual) / (norma_referencia * norma_actual))
    return similitud if np.isfinite(similitud) else 0.0