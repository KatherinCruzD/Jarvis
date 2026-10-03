import re
import os
import threading
import time
from collections import deque
from collections.abc import Callable

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from faster_whisper import WhisperModel

from voz import mi_voz

load_dotenv()

FRECUENCIA = 16000
PASO = 0.1
UMBRAL_SONIDO = 0.01
SILENCIO_FIN = 1.5
MAXIMO_FRASE = 30.0
MAXIMO_INTERRUPCION = 2.5
MINIMO_FRASE = 1.0
SEGUNDOS_CONVERSACION = 20
PALABRAS = ("jarvis", "yarvis", "jarbis", "yarbis", "harvis", "charvis")

FRASES_FALSAS = ("suscrib", "gracias por ver", "subtítulos", "amara.org")

pausa = threading.Event()
parar = threading.Event()
procesando = threading.Event()
interrumpir_habla = threading.Event()
privado = threading.Event()
_modelo = None


def _configuracion_whisper() -> tuple[str, str, str, int]:
    tamano = os.getenv("JARVIS_WHISPER_MODEL", "small").strip().casefold()
    dispositivo = os.getenv("JARVIS_WHISPER_DEVICE", "cpu").strip().casefold()
    tipo_calculo = os.getenv("JARVIS_WHISPER_COMPUTE_TYPE", "int8").strip().casefold()
    try:
        beam_size = int(os.getenv("JARVIS_WHISPER_BEAM_SIZE", "5"))
    except ValueError as error:
        raise ValueError("JARVIS_WHISPER_BEAM_SIZE debe ser un número entre 1 y 10.") from error

    if tamano not in {"tiny", "base", "small", "medium", "large-v3"}:
        raise ValueError(
            "JARVIS_WHISPER_MODEL debe ser tiny, base, small, medium o large-v3."
        )
    if dispositivo not in {"cpu", "cuda", "auto"}:
        raise ValueError("JARVIS_WHISPER_DEVICE debe ser cpu, cuda o auto.")
    if not 1 <= beam_size <= 10:
        raise ValueError("JARVIS_WHISPER_BEAM_SIZE debe estar entre 1 y 10.")
    return tamano, dispositivo, tipo_calculo, beam_size


def _dispositivo_microfono() -> int | None:
    configurado = os.getenv("JARVIS_MIC_DEVICE", "").strip()
    dispositivos = [
        (indice, dispositivo)
        for indice, dispositivo in enumerate(sd.query_devices())
        if int(dispositivo.get("max_input_channels", 0)) > 0
    ]
    if not dispositivos:
        raise RuntimeError("Windows no muestra ningún micrófono disponible para Jarvis.")
    if not configurado:
        return None

    if configurado.isdecimal():
        indice = int(configurado)
        if any(numero == indice for numero, _ in dispositivos):
            return indice
    else:
        coincidencias = [
            indice
            for indice, dispositivo in dispositivos
            if configurado.casefold() in str(dispositivo.get("name", "")).casefold()
        ]
        if len(coincidencias) == 1:
            return coincidencias[0]
        if len(coincidencias) > 1:
            opciones = ", ".join(map(str, coincidencias))
            raise ValueError(
                f"JARVIS_MIC_DEVICE coincide con varios micrófonos ({opciones}); "
                "usa el número del dispositivo."
            )

    disponibles = "; ".join(
        f"{indice}: {dispositivo['name']}" for indice, dispositivo in dispositivos
    )
    raise ValueError(
        f"No encontré el micrófono configurado {configurado!r}. "
        f"Entradas disponibles: {disponibles}"
    )


def _whisper():
    global _modelo
    if _modelo is None:
        tamano, dispositivo, tipo_calculo, beam_size = _configuracion_whisper()
        print(
            f"[oído] Whisper {tamano}, {dispositivo}/{tipo_calculo}, "
            f"beam={beam_size}"
        )
        _modelo = WhisperModel(
            tamano,
            device=dispositivo,
            compute_type=tipo_calculo,
        )
    return _modelo


def transcribir(audio) -> str:
    _, _, _, beam_size = _configuracion_whisper()
    segmentos, _ = _whisper().transcribe(
        audio,
        language="es",
        beam_size=beam_size,
        temperature=0.0,
        vad_filter=True,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        initial_prompt=(
            "Jarvis, abre Word, WhatsApp, Spotify, Outlook o Google Drive. "
            "Busca un archivo, crea una carpeta o reproduce una canción."
        ),
    )
    texto = " ".join(s.text.strip() for s in segmentos).strip()
    if any(frase in texto.lower() for frase in FRASES_FALSAS):
        return ""
    return texto


def quitar_activacion(texto):
    activacion = "|".join(re.escape(palabra) for palabra in PALABRAS)
    coincidencia = re.match(
        rf"^\s*(?:oye\s+)?(?:{activacion})\b[\s,.:;!¡¿?—-]*",
        texto,
        flags=re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    return texto[coincidencia.end() :].strip(" ,.:;!¡¿?—-")


def grabar_frase(
    interrumpir: Callable[[np.ndarray], np.ndarray | None] | None = None,
    dispositivo: int | None = None,
):
    previos = deque(maxlen=3)
    bloques = []
    hablo = False
    silencio = 0.0
    duracion = 0.0
    tamano = int(FRECUENCIA * PASO)
    detector_interrupcion = interrumpir
    estaba_pausado = False

    with sd.InputStream(
        samplerate=FRECUENCIA,
        channels=1,
        dtype="float32",
        blocksize=tamano,
        device=dispositivo,
    ) as flujo:
        while not parar.is_set():
            datos, _ = flujo.read(tamano)
            if privado.is_set():
                return None
            if pausa.is_set():
                if detector_interrupcion is None:
                    detector_interrupcion = DetectorInterrupcion()
                audio_interrupcion = detector_interrupcion(datos)
                if audio_interrupcion is not None:
                    return audio_interrupcion
                previos.clear()
                bloques, hablo, silencio, duracion = [], False, 0.0, 0.0
                estaba_pausado = True
                continue
            if procesando.is_set():
                previos.clear()
                bloques, hablo, silencio, duracion = [], False, 0.0, 0.0
                continue
            if estaba_pausado:
                detector_interrupcion._reiniciar()
                estaba_pausado = False
                previos.clear()
                bloques, hablo, silencio, duracion = [], False, 0.0, 0.0
                continue

            volumen = float(np.sqrt(np.mean(datos ** 2)))
            if volumen > UMBRAL_SONIDO:
                if not hablo:
                    hablo = True
                    print("[oído] detecté sonido")
                    bloques.extend(previos)
                silencio = 0.0
            elif hablo:
                silencio += PASO
            else:
                previos.append(datos.copy())

            if hablo:
                bloques.append(datos.copy())
                duracion += PASO
                if silencio >= SILENCIO_FIN or duracion >= MAXIMO_FRASE:
                    break

    if not bloques or duracion < MINIMO_FRASE:
        return None
    return np.concatenate(bloques).flatten()


class DetectorInterrupcion:
    def __init__(self):
        self.previos = deque(maxlen=5)
        self.bloques = []
        self.hablando = False
        self.silencio = 0.0
        self.duracion = 0.0
        self.activacion_detectada = False
        self.audio: np.ndarray | None = None
        self.texto: str | None = None

    def __call__(self, datos: np.ndarray) -> np.ndarray | None:
        volumen = float(np.sqrt(np.mean(datos ** 2)))
        if volumen > UMBRAL_SONIDO:
            if not self.hablando:
                self.hablando = True
                self.bloques.extend(self.previos)
            self.silencio = 0.0
        elif self.hablando:
            self.silencio += PASO
        else:
            self.previos.append(datos.copy())

        if self.hablando:
            self.bloques.append(datos.copy())
            self.duracion += PASO

        if self.silencio < 0.7 and self.duracion < MAXIMO_INTERRUPCION:
            return None

        audio = np.concatenate(self.bloques).flatten() if self.bloques else None
        self._reiniciar()
        if audio is None or len(audio) < FRECUENCIA:
            return None

        maximo = float(np.abs(audio).max())
        if not np.isfinite(audio).all() or maximo < 0.03:
            return None

        texto = transcribir((audio / maximo * 0.9).astype(np.float32))
        if quitar_activacion(texto) is None:
            return None

        self.activacion_detectada = True
        interrumpir_habla.set()

        similitud = mi_voz.parecido(audio)
        if not np.isfinite(similitud) or similitud < mi_voz.UMBRAL_VOZ:
            print("[oído] activación detectada, pero la voz no fue autorizada")
            return None

        self.audio = audio
        self.texto = texto
        return audio

    def _reiniciar(self) -> None:
        self.previos.clear()
        self.bloques = []
        self.hablando = False
        self.silencio = 0.0
        self.duracion = 0.0


def bucle(al_comando, al_estado):
    dispositivo = _dispositivo_microfono()
    descripcion = sd.query_devices(dispositivo, kind="input")
    print(
        f"[oído] micrófono: {descripcion['name']} "
        f"(entrada {dispositivo if dispositivo is not None else 'predeterminada'})"
    )
    _whisper()
    mi_voz._encoder()
    print("[oído] listo, esperando tu voz...")
    ventana_hasta = 0.0
    while not parar.is_set():
        while privado.is_set() and not parar.wait(0.1):
            pass
        if parar.is_set():
            break
        detector_interrupcion = DetectorInterrupcion()
        if dispositivo is None:
            audio = grabar_frase(detector_interrupcion)
        else:
            audio = grabar_frase(detector_interrupcion, dispositivo)
        if audio is None:
            if detector_interrupcion.activacion_detectada:
                ventana_hasta = time.monotonic() + SEGUNDOS_CONVERSACION
                print(
                    "[oído] detuve la lectura; di tu orden otra vez dentro de "
                    f"{SEGUNDOS_CONVERSACION} segundos"
                )
            continue
        if privado.is_set():
            continue
        maximo = float(np.abs(audio).max())
        print(f"[oído] {len(audio) / FRECUENCIA:.1f} s, volumen máximo {maximo:.2f}")
        if maximo < 0.03:
            print("[oído] muy bajito, lo ignoro")
            continue
        valor = mi_voz.parecido(audio)
        print(f"[oído] parecido con tu voz: {valor:.2f} (necesito {mi_voz.UMBRAL_VOZ})")
        if not np.isfinite(valor) or valor < mi_voz.UMBRAL_VOZ:
            al_estado("reposo")
            continue
        al_estado("escuchando")
        pausa.clear()
        if audio is detector_interrupcion.audio:
            texto = detector_interrupcion.texto or ""
        else:
            audio_transcripcion = (audio / maximo * 0.9).astype(np.float32)
            texto = transcribir(audio_transcripcion)
        print(f"[oído] entendí: {texto!r}")
        comando = quitar_activacion(texto) if texto else None
        if comando is None and texto and time.monotonic() < ventana_hasta:
            comando = texto
        if comando is None:
            if texto and quitar_activacion(texto) == "":
                procesando.set()
                al_comando("")
            al_estado("reposo")
            continue
        procesando.set()
        al_comando(comando)
        ventana_hasta = time.monotonic() + SEGUNDOS_CONVERSACION
        if not parar.is_set():
            al_estado("reposo")