from pathlib import Path

import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav

FRECUENCIA = 16000
ARCHIVO = Path(__file__).resolve().parent / "mi_voz.npy"
UMBRAL_VOZ = 0.75

_codificador = None


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


def cargar_huella():
    return np.load(ARCHIVO) if ARCHIVO.exists() else None

def parecido(audio) -> float:
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

    similitud = float(
        np.dot(referencia, actual) / (norma_referencia * norma_actual)
    )
    return similitud if np.isfinite(similitud) else 0.0