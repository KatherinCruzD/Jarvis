import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import numpy as np
from fastapi import WebSocketDisconnect

from core.acciones import (
    abrir_url_segura,
    ejecutar_atajo,
    interpretar_atajo,
    interpretar_spotify,
    interpretar_youtube,
)
from core import memoria
from core.archivos import (
    interpretar_apertura,
    interpretar_busqueda,
    interpretar_crear_carpeta_drive,
    interpretar_subida_drive,
)
from core.spotify import reproducir_cancion
from core.google_drive import subir_archivo
from core.word import (
    aplicar_apa_a_elemento,
    aplicar_formato_apa,
    insertar_portada_apa,
    insertar_texto_documento,
    interpretar_formato_apa,
    interpretar_formato_elemento_apa,
    interpretar_portada_apa,
    interpretar_seccion_documento,
    interpretar_texto_documento,
)
from core.whatsapp import interpretar_mensaje as interpretar_mensaje_whatsapp
from core.whatsapp import preparar_mensaje as preparar_mensaje_whatsapp
from core.youtube import abrir_cancion as abrir_cancion_youtube
from servidor import app as servidor
from voz.hablar import hablar
from voz import mi_voz, oido
from voz.interrupcion import vigilar_f8


class VoiceCommandTests(unittest.TestCase):
    def tearDown(self):
        oido.parar.clear()
        oido.pausa.clear()
        oido.interrumpir_habla.clear()

    def test_activation_is_removed_only_at_start(self):
        self.assertEqual(oido.quitar_activacion("Jarvis, abre Word"), "abre Word")
        self.assertEqual(oido.quitar_activacion("Oye Jarvis: duérmete"), "duérmete")
        self.assertIsNone(oido.quitar_activacion("Por favor, Jarvis abre Word"))

    def test_other_voice_is_rejected_before_transcription(self):
        audio = np.full(FRECUENCIA_DOS_SEGUNDOS, 0.1, dtype=np.float32)

        def capturar(interruptor):
            self.assertIsInstance(interruptor, oido.DetectorInterrupcion)
            oido.parar.set()
            return audio

        with (
            patch.object(oido, "_whisper"),
            patch.object(mi_voz, "_encoder"),
            patch.object(mi_voz, "parecido", return_value=0.2),
            patch.object(oido, "transcribir") as transcribir,
            patch.object(oido, "grabar_frase", side_effect=capturar),
        ):
            oido.parar.clear()
            oido.bucle(lambda _: self.fail("No debe despachar voz no autorizada"), lambda _: None)

        transcribir.assert_not_called()

    def test_invalid_voice_similarity_fails_closed(self):
        for referencia, actual in (
            (np.array([np.nan, 1.0]), np.array([1.0, 1.0])),
            (np.zeros(2), np.ones(2)),
            (np.ones(2), np.zeros(2)),
        ):
            with (
                self.subTest(referencia=referencia, actual=actual),
                patch.object(mi_voz, "cargar_huella", return_value=referencia),
                patch.object(mi_voz, "huella", return_value=actual),
            ):
                self.assertEqual(mi_voz.parecido(np.ones(2)), 0.0)

        audio = np.full(FRECUENCIA_DOS_SEGUNDOS, 0.1, dtype=np.float32)

        def capturar(interruptor):
            self.assertIsInstance(interruptor, oido.DetectorInterrupcion)
            oido.parar.set()
            return audio

        with (
            patch.object(oido, "_whisper"),
            patch.object(mi_voz, "_encoder"),
            patch.object(mi_voz, "parecido", return_value=float("nan")),
            patch.object(oido, "transcribir") as transcribir,
            patch.object(oido, "grabar_frase", side_effect=capturar),
        ):
            oido.parar.clear()
            oido.bucle(lambda _: self.fail("Una similitud inválida no se autoriza"), lambda _: None)

        transcribir.assert_not_called()

    def test_owner_voice_dispatches_command_without_normalizing_auth_audio(self):
        audio = np.full(FRECUENCIA_DOS_SEGUNDOS, 0.1, dtype=np.float32)
        comandos = []

        def capturar(interruptor):
            self.assertIsInstance(interruptor, oido.DetectorInterrupcion)
            oido.parar.set()
            return audio

        with (
            patch.object(oido, "_whisper"),
            patch.object(mi_voz, "_encoder"),
            patch.object(mi_voz, "parecido", return_value=0.95) as parecido,
            patch.object(oido, "transcribir", return_value="Jarvis, abre Word"),
            patch.object(oido, "grabar_frase", side_effect=capturar),
        ):
            oido.parar.clear()
            oido.bucle(comandos.append, lambda _: None)

        np.testing.assert_array_equal(parecido.call_args.args[0], audio)
        self.assertEqual(comandos, ["abre Word"])

    def test_hands_free_window_starts_after_jarvis_finishes_responding(self):
        audio = np.full(FRECUENCIA_DOS_SEGUNDOS, 0.1, dtype=np.float32)
        frases = iter(["Jarvis, hola", "continúa"])
        reloj = SimpleNamespace(ahora=10.0)
        capturas = 0
        comandos = []

        def capturar(interruptor):
            self.assertIsInstance(interruptor, oido.DetectorInterrupcion)
            nonlocal capturas
            capturas += 1
            if capturas == 2:
                oido.parar.set()
            return audio

        def procesar(comando):
            comandos.append(comando)
            reloj.ahora = 40.0

        with (
            patch.object(oido, "_whisper"),
            patch.object(mi_voz, "_encoder"),
            patch.object(mi_voz, "parecido", return_value=0.95),
            patch.object(oido, "transcribir", side_effect=lambda _: next(frases)),
            patch.object(oido, "grabar_frase", side_effect=capturar),
            patch.object(oido.time, "monotonic", side_effect=lambda: reloj.ahora),
        ):
            oido.parar.clear()
            oido.bucle(procesar, lambda _: None)

        self.assertEqual(comandos, ["hola", "continúa"])

    def test_owner_can_interrupt_speech_and_submit_the_new_command(self):
        bloque_voz = np.full(int(oido.FRECUENCIA * oido.PASO), 0.1, dtype=np.float32)
        bloque_silencio = np.zeros_like(bloque_voz)
        oido.interrumpir_habla.clear()
        detector = oido.DetectorInterrupcion()

        with (
            patch.object(mi_voz, "parecido", return_value=0.95),
            patch.object(oido, "transcribir", return_value="Jarvis, abre Word"),
        ):
            for _ in range(11):
                self.assertIsNone(detector(bloque_voz))
            audio = None
            for _ in range(8):
                audio = detector(bloque_silencio)
                if audio is not None:
                    break

        self.assertIsNotNone(audio)
        self.assertIsInstance(audio, np.ndarray)
        np.testing.assert_array_equal(audio[-len(bloque_silencio):], bloque_silencio)
        self.assertTrue(oido.interrumpir_habla.is_set())
        self.assertEqual(oido.quitar_activacion("Jarvis, abre Word"), "abre Word")
        oido.interrumpir_habla.clear()

    def test_wake_word_alone_is_enough_to_interrupt_tts(self):
        bloque_voz = np.full(int(oido.FRECUENCIA * oido.PASO), 0.1, dtype=np.float32)
        bloque_silencio = np.zeros_like(bloque_voz)
        detector = oido.DetectorInterrupcion()
        oido.interrumpir_habla.clear()

        with (
            patch.object(mi_voz, "parecido", return_value=0.95),
            patch.object(oido, "transcribir", return_value="Jarvis."),
        ):
            for _ in range(11):
                detector(bloque_voz)
            audio = None
            for _ in range(8):
                audio = detector(bloque_silencio)
                if audio is not None:
                    break

        self.assertIsNotNone(audio)
        self.assertTrue(oido.interrumpir_habla.is_set())
        self.assertEqual(oido.quitar_activacion("Jarvis."), "")
        oido.interrumpir_habla.clear()

    def test_active_microphone_stream_switches_to_interrupt_detection(self):
        bloque = np.full(int(oido.FRECUENCIA * oido.PASO), 0.1, dtype=np.float32)
        voz_detectada = np.full(oido.FRECUENCIA, 0.2, dtype=np.float32)

        class Flujo:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, _):
                oido.pausa.set()
                return bloque, None

        detector = Mock(return_value=voz_detectada)
        oido.pausa.clear()
        with patch.object(oido.sd, "InputStream", return_value=Flujo()):
            resultado = oido.grabar_frase(detector)

        self.assertIs(resultado, voz_detectada)
        detector.assert_called_once_with(bloque)
        oido.pausa.clear()

    def test_other_voice_can_stop_tts_but_cannot_submit_a_command(self):
        bloque_voz = np.full(int(oido.FRECUENCIA * oido.PASO), 0.1, dtype=np.float32)
        bloque_silencio = np.zeros_like(bloque_voz)
        detector = oido.DetectorInterrupcion()
        with (
            patch.object(mi_voz, "parecido", return_value=0.2),
            patch.object(oido, "transcribir", return_value="Jarvis, abre Word") as transcribir,
        ):
            for _ in range(11):
                detector(bloque_voz)
            for _ in range(8):
                audio = detector(bloque_silencio)
                if audio is not None:
                    break

        self.assertIsNone(audio)
        self.assertTrue(oido.interrumpir_habla.is_set())
        self.assertTrue(detector.activacion_detectada)
        self.assertIsNone(detector.audio)
        transcribir.assert_called_once()
        oido.interrumpir_habla.clear()

    def test_owner_can_repeat_command_after_unverified_barge_in(self):
        audio = np.full(FRECUENCIA_DOS_SEGUNDOS, 0.1, dtype=np.float32)
        capturas = 0
        comandos = []

        def capturar(detector):
            nonlocal capturas
            capturas += 1
            if capturas == 1:
                detector.activacion_detectada = True
                return None
            oido.parar.set()
            return audio

        with (
            patch.object(oido, "_whisper"),
            patch.object(mi_voz, "_encoder"),
            patch.object(mi_voz, "parecido", return_value=0.95),
            patch.object(oido, "transcribir", return_value="abre Word"),
            patch.object(oido, "grabar_frase", side_effect=capturar),
            patch.object(oido.time, "monotonic", return_value=10.0),
        ):
            oido.parar.clear()
            oido.bucle(comandos.append, lambda _: None)

        self.assertEqual(comandos, ["abre Word"])

    def test_tts_process_is_terminated_when_interrupt_event_is_set(self):
        class ProcesoFalso:
            returncode = 0
            args = ["powershell"]

            def __init__(self):
                self.terminado = False

            def poll(self):
                return None if not self.terminado else 0

            def terminate(self):
                self.terminado = True

            def wait(self, timeout=None):
                self.asserted_timeout = timeout
                return 0

        proceso = ProcesoFalso()
        cancelar = Event()
        cancelar.set()
        with patch("voz.hablar.subprocess.Popen", return_value=proceso) as popen:
            hablar("Texto de prueba", cancelar)

        popen.assert_called_once()
        self.assertTrue(proceso.terminado)

    def test_f8_stops_speech_from_a_background_keyboard_listener(self):
        hablando = Event()
        hablando.set()
        detener = Event()
        interrumpir = Event()
        lecturas = iter([False, True])
        esperas = 0

        class DetenerEnSiguienteLectura:
            def wait(self, _):
                nonlocal esperas
                esperas += 1
                return esperas == 3

        vigilar_f8(
            DetenerEnSiguienteLectura(),
            hablando,
            interrumpir,
            leer_tecla=lambda: next(lecturas),
        )

        self.assertTrue(interrumpir.is_set())

    def test_microphone_can_be_selected_by_name_fragment_or_device_id(self):
        dispositivos = [
            {"name": "Laptop Microphone", "max_input_channels": 1},
            {"name": "USB Studio Microphone", "max_input_channels": 1},
            {"name": "Speakers", "max_input_channels": 0},
        ]
        with (
            patch.dict(os.environ, {"JARVIS_MIC_DEVICE": "studio"}),
            patch.object(oido.sd, "query_devices", return_value=dispositivos),
        ):
            self.assertEqual(oido._dispositivo_microfono(), 1)
        with (
            patch.dict(os.environ, {"JARVIS_MIC_DEVICE": "1"}),
            patch.object(oido.sd, "query_devices", return_value=dispositivos),
        ):
            self.assertEqual(oido._dispositivo_microfono(), 1)

    def test_whisper_configuration_can_reduce_cpu_cost(self):
        with patch.dict(
            os.environ,
            {
                "JARVIS_WHISPER_MODEL": "base",
                "JARVIS_WHISPER_DEVICE": "cpu",
                "JARVIS_WHISPER_COMPUTE_TYPE": "int8",
                "JARVIS_WHISPER_BEAM_SIZE": "3",
            },
        ):
            self.assertEqual(
                oido._configuracion_whisper(),
                ("base", "cpu", "int8", 3),
            )

    def test_local_memory_only_saves_explicit_and_deletes_exact_match(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "memoria.sqlite3"
            with patch.object(memoria, "ruta_memoria", return_value=ruta):
                self.assertEqual(
                    memoria.recordar("Mi color favorito es azul"),
                    "Lo recordaré: Mi color favorito es azul",
                )
                self.assertEqual(
                    memoria.buscar("¿Qué color me gusta?"),
                    ["Mi color favorito es azul"],
                )
                self.assertIn("idéntico", memoria.olvidar("me gusta el verde"))
                self.assertIn("Olvidé", memoria.olvidar("mi color favorito es azul"))
                self.assertEqual(memoria.listar(), [])

    def test_memory_commands_accept_accents_and_capture_fact(self):
        self.assertEqual(
            memoria.interpretar_recuerdo("recuerda que mi color favorito es azul"),
            "mi color favorito es azul",
        )
        self.assertEqual(
            memoria.interpretar_consulta_memoria(
                "¿Qué recuerdas de mi color favorito?"
            ),
            "mi color favorito",
        )
        self.assertEqual(
            memoria.interpretar_consulta_memoria("muéstrame mis recuerdos"),
            "",
        )
        self.assertEqual(
            memoria.interpretar_olvidar("olvida mi color favorito es azul"),
            "mi color favorito es azul",
        )

    def test_open_commands_are_allowlisted(self):
        self.assertEqual(interpretar_atajo("abre Word"), "word")
        self.assertEqual(interpretar_atajo("Jarvis abre Gmail"), "gmail")
        self.assertEqual(interpretar_atajo("abre el correo Gmail"), "gmail")
        self.assertEqual(interpretar_atajo("abre mi correo de Gmail"), "gmail")
        self.assertEqual(interpretar_atajo("abre correo"), "outlook")
        self.assertEqual(interpretar_atajo("Jarvis, abre VS Code"), "vscode")
        self.assertEqual(interpretar_atajo("abre VS"), "vscode")
        self.assertEqual(interpretar_atajo("abre visual studio"), "vscode")
        self.assertEqual(interpretar_atajo("abre WhatsApp"), "whatsapp")
        self.assertEqual(interpretar_atajo("abre Roblox."), "roblox")
        self.assertEqual(interpretar_atajo("Jarvis, entrar a PSeInt"), "pseint")
        self.assertEqual(interpretar_atajo("abre PSeInt"), "pseint")
        self.assertIsNone(interpretar_atajo("ejecuta cmd /c del *"))

    def test_web_shortcuts_use_windows_default_browser(self):
        for destino, url in (
            ("gmail", "https://mail.google.com"),
            ("drive", "https://drive.google.com"),
        ):
            with self.subTest(destino=destino), patch(
                "core.acciones.os.startfile", create=True
            ) as abrir_url:
                respuesta = ejecutar_atajo(destino)

            abrir_url.assert_called_once_with(url)
            self.assertIn("Abriendo", respuesta)

    def test_safe_web_opener_rejects_non_https_urls(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            abrir_url_segura("javascript:alert(1)")

    def test_word_and_vscode_launch_with_resolved_absolute_executables(self):
        word = Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE")
        vscode = Path(r"C:\Program Files\Microsoft VS Code\Code.exe")
        with (
            patch("core.acciones._resolver_ejecutable", side_effect=[word, vscode]),
            patch("core.acciones.subprocess.Popen") as iniciar,
        ):
            self.assertEqual(ejecutar_atajo("word"), "Abriendo Microsoft Word.")
            self.assertEqual(ejecutar_atajo("vscode"), "Abriendo Visual Studio Code.")

        self.assertEqual(
            [llamada.args[0] for llamada in iniciar.call_args_list],
            [[str(word)], [str(vscode)]],
        )
        self.assertTrue(all(llamada.kwargs["shell"] is False for llamada in iniciar.call_args_list))

    def test_pseint_opens_from_its_installed_program_folder(self):
        pseint = Path(r"C:\Program Files (x86)\PSeInt\pseint.exe")
        with (
            patch(
                "core.acciones.Path.is_file",
                autospec=True,
                side_effect=lambda ruta: ruta == pseint,
            ),
            patch("core.acciones.subprocess.Popen") as iniciar,
        ):
            respuesta = ejecutar_atajo("pseint")

        self.assertEqual(respuesta, "Abriendo PSeInt.")
        self.assertEqual(iniciar.call_args.args[0], [str(pseint)])
        self.assertFalse(iniciar.call_args.kwargs["shell"])

    def test_uninstalled_program_reports_a_clear_error(self):
        with patch("core.acciones._resolver_ejecutable", side_effect=FileNotFoundError("Word no instalado")):
            with self.assertRaisesRegex(FileNotFoundError, "Word no instalado"):
                ejecutar_atajo("word")

    def test_voice_file_and_drive_commands_are_parsed(self):
        self.assertEqual(
            interpretar_busqueda("busca en el explorador de archivos un archivo llamado notas"),
            "notas",
        )
        self.assertEqual(
            interpretar_apertura("abre el archivo llamado informe.pdf en la carpeta Tareas"),
            ("informe.pdf", "Tareas"),
        )
        self.assertEqual(
            interpretar_busqueda(
                "Jarvis busca en el explorador de archivos un documento llamado notas"
            ),
            "notas",
        )
        self.assertEqual(
            interpretar_busqueda("buscar el archivo que se llama notas"),
            "notas",
        )
        self.assertEqual(
            interpretar_apertura("Jarvis, abre un documento llamado tarea.docx"),
            ("tarea.docx", None),
        )
        self.assertEqual(
            interpretar_crear_carpeta_drive("crea una carpeta en drive llamada Proyectos"),
            "Proyectos",
        )
        self.assertEqual(
            interpretar_subida_drive("sube a Google Drive el archivo informe.pdf"),
            ("informe.pdf", None),
        )
        self.assertEqual(
            interpretar_subida_drive(
                "sube el archivo informe.pdf a Drive en la carpeta Tareas"
            ),
            ("informe.pdf", "Tareas"),
        )

    def test_spotify_playback_selects_top_search_result_and_active_device(self):
        with (
            patch.dict(os.environ, {"JARVIS_SPOTIFY_CLIENT_ID": "client-id"}),
            patch(
                "core.spotify._spotify",
                side_effect=[
                    {
                        "tracks": {
                            "items": [
                                {
                                    "name": "Canción",
                                    "artists": [{"name": "Artista"}],
                                    "uri": "spotify:track:abc",
                                }
                            ]
                        }
                    },
                    {"devices": [{"id": "device-1", "is_active": True}]},
                    {},
                ],
            ) as spotify,
        ):
            respuesta = reproducir_cancion("Canción")

        self.assertEqual(respuesta, "Reproduciendo Canción de Artista en Spotify.")
        self.assertEqual(
            spotify.call_args_list[-1].args,
            ("PUT", "me/player/play?device_id=device-1", {"uris": ["spotify:track:abc"]}),
        )

    def test_spotify_free_account_opens_search_without_api_setup(self):
        with (
            patch.dict(os.environ, {"JARVIS_SPOTIFY_CLIENT_ID": ""}),
            patch("core.spotify.abrir_busqueda_spotify") as buscar,
            patch("core.spotify._spotify") as api,
        ):
            respuesta = reproducir_cancion("mi canción")

        buscar.assert_called_once_with("mi canción")
        api.assert_not_called()
        self.assertIn("cuenta gratis", respuesta)
        self.assertIn("sin Premium", respuesta)

    def test_spotify_premium_api_denial_falls_back_to_free_search(self):
        with (
            patch.dict(os.environ, {"JARVIS_SPOTIFY_CLIENT_ID": "client-id"}),
            patch(
                "core.spotify._spotify",
                side_effect=RuntimeError(
                    "Spotify no autorizó la reproducción. Se requiere Spotify "
                    "Premium y un dispositivo de reproducción activo."
                ),
            ),
            patch("core.spotify.abrir_busqueda_spotify") as buscar,
        ):
            respuesta = reproducir_cancion("mi canción")

        buscar.assert_called_once_with("mi canción")
        self.assertIn("cuenta gratis", respuesta)

    def test_spotify_commands_accept_both_natural_word_orders(self):
        self.assertEqual(
            interpretar_spotify("Jarvis, abre Spotify y reproduce Eres"),
            ("reproduce", "Eres"),
        )
        self.assertEqual(
            interpretar_spotify("Jarvis, reproduce Eres en Spotify"),
            ("reproduce", "Eres"),
        )
        self.assertEqual(
            interpretar_spotify("pon Eres en Spotify"),
            ("pon", "Eres"),
        )
        self.assertEqual(
            interpretar_spotify("Jarvis, abre Spotify y busca Eres"),
            ("busca", "Eres"),
        )

    def test_apa_commands_are_explicit_and_bounded(self):
        for comando in (
            "Jarvis ponle normas APA al documento en blanco que abriste",
            "Jarvis, ponle normas APA edición 7 al documento",
            "poner normas APA a mi documento",
            "Jarvis, aplica las normas APA 7 a mi documento",
            "pon mi documento en formato APA",
            "aplica formato APA 7 al documento",
            "formatea el documento en APA 7",
        ):
            with self.subTest(comando=comando):
                self.assertTrue(interpretar_formato_apa(comando))
        self.assertFalse(interpretar_formato_apa("pon formato APA a todos mis archivos"))

    def test_word_text_commands_preserve_the_requested_text(self):
        for comando, esperado in (
            (
                'Jarvis, escribe en el documento: "Mi texto, con comas."',
                "Mi texto, con comas.",
            ),
            (
                "Jarvis, escribe en el documento: “La energía solar ayuda.”",
                "La energía solar ayuda.",
            ),
            (
                "Jarvis, pon en el documento el siguiente texto: La energía solar ayuda.",
                "La energía solar ayuda.",
            ),
            (
                "Jarvis, pon La energía solar ayuda en el documento de Word.",
                "La energía solar ayuda",
            ),
            ("escribe en mi documento que diga Hola Jarvis", "Hola Jarvis"),
            ("escribe la introducción del documento", None),
            ("escribe en el documento", None),
        ):
            with self.subTest(comando=comando):
                self.assertEqual(interpretar_texto_documento(comando), esperado)

    def test_word_cover_table_figure_and_section_commands_are_parsed(self):
        self.assertEqual(
            interpretar_portada_apa(
                "Jarvis, crea una portada APA con el título: La educación local"
            ),
            "La educación local",
        )
        self.assertEqual(
            interpretar_formato_elemento_apa(
                "aplica normas APA a esta tabla seleccionada"
            ),
            "tabla",
        )
        self.assertEqual(
            interpretar_formato_elemento_apa("ponle normas APA a la tabla"),
            "tabla",
        )
        self.assertEqual(
            interpretar_formato_elemento_apa("pon formato APA a la imagen"),
            "imagen",
        )
        self.assertEqual(
            interpretar_seccion_documento("redacta la introducción del documento"),
            "Introducción",
        )
        self.assertEqual(
            interpretar_seccion_documento("crea los objetivos"),
            "Objetivos",
        )
        self.assertEqual(
            interpretar_seccion_documento("genera las conclusiones del trabajo"),
            "Conclusiones",
        )

    def test_whatsapp_message_parser_preserves_contact_and_message(self):
        self.assertEqual(
            interpretar_mensaje_whatsapp(
                'Jarvis, envía a mamá un mensaje de "Hola, ¿cómo estás?"'
            ),
            ("mamá", "Hola, ¿cómo estás?"),
        )
        self.assertEqual(
            interpretar_mensaje_whatsapp(
                "mandale a Ana un mensaje que diga Te llamo mañana"
            ),
            ("Ana", "Te llamo mañana"),
        )
        self.assertEqual(
            interpretar_mensaje_whatsapp(
                'envía a Carlos Pérez un mensaje de "Llego en 10 minutos"'
            ),
            ("Carlos Pérez", "Llego en 10 minutos"),
        )

    def test_whatsapp_draft_prepares_clipboard_and_opens_allowlisted_app(self):
        with (
            patch("core.whatsapp.abrir_url_segura") as abrir,
        ):
            respuesta = preparar_mensaje_whatsapp("Carlos Pérez", "Hola")

        abrir.assert_called_once_with("https://wa.me/?text=Hola")
        self.assertIn("Carlos Pérez", respuesta)
        self.assertIn("Elige manualmente", respuesta)
        self.assertIn("no envió", respuesta)

    def test_youtube_commands_open_a_free_autoplay_watch_page(self):
        identificador = "abcdefghijk"
        with (
            patch(
                "core.youtube.YoutubeDL"
            ) as extractor_class,
            patch("core.youtube.abrir_url_segura") as abrir,
        ):
            extractor = extractor_class.return_value.__enter__.return_value
            extractor.extract_info.return_value = {
                "entries": [{"id": identificador, "title": "Canción de prueba"}]
            }
            respuesta = abrir_cancion_youtube("Canción de prueba")

        extractor.extract_info.assert_called_once_with(
            "ytsearch1:Canción de prueba", download=False
        )
        self.assertEqual(
            abrir.call_args.args[0],
            "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1",
        )
        self.assertIn("gratis", respuesta)

    def test_youtube_search_commands_are_parsed(self):
        self.assertEqual(
            interpretar_youtube("Jarvis, pon Despacito en YouTube"),
            ("pon", "Despacito"),
        )
        self.assertEqual(
            interpretar_youtube("abre YouTube y reproduce Despacito"),
            ("reproduce", "Despacito"),
        )

    def test_file_search_finds_files_anywhere_in_profile_but_skips_appdata(self):
        with tempfile.TemporaryDirectory() as temp:
            perfil = Path(temp)
            archivo = perfil / "Proyectos" / "2026" / "informe_final.docx"
            archivo.parent.mkdir(parents=True)
            archivo.touch()
            oculto = perfil / "AppData" / "Roaming" / "informe_final.docx"
            oculto.parent.mkdir(parents=True)
            oculto.touch()

            with (
                patch("core.archivos.raices_busqueda", return_value=(perfil,)),
                patch("core.archivos._buscar_indice_windows", return_value=[]),
            ):
                from core.archivos import buscar_archivos

                resultados = buscar_archivos("informe_final")

        self.assertEqual(resultados, [archivo])

    def test_drive_upload_only_accepts_files_in_personal_folders(self):
        with tempfile.TemporaryDirectory() as temp:
            perfil = Path(temp) / "perfil"
            documentos = perfil / "Documents"
            documentos.mkdir(parents=True)
            archivo_permitido = documentos / "informe.txt"
            archivo_permitido.write_text("contenido de prueba", encoding="utf-8")
            archivo_privado = perfil / "AppData" / "secreto.txt"
            archivo_privado.parent.mkdir()
            archivo_privado.write_text("privado", encoding="utf-8")

            with (
                patch(
                    "core.google_drive.raices_archivos_personales",
                    return_value=(documentos,),
                ),
                patch(
                    "core.google_drive._solicitud_drive",
                    return_value={"name": "informe.txt"},
                ) as subir,
            ):
                respuesta = subir_archivo(archivo_permitido)

                with self.assertRaises(PermissionError):
                    subir_archivo(archivo_privado)

        subir.assert_called_once()
        self.assertIn("informe.txt", respuesta)

    def test_apa_format_uses_active_word_and_does_not_save_automatically(self):
        with (
            patch("core.word._documento_activo") as activo,
        ):
            pythoncom = Mock()
            documento = Mock()
            documento.Name = "Documento de prueba.docx"
            documento.Sections = []
            activo.return_value = (pythoncom, True, Mock(), documento)
            self.assertIn("Documento de prueba.docx", aplicar_formato_apa())

        documento.Content.Font.Name = "Times New Roman"
        self.assertEqual(documento.Content.Font.Name, "Times New Roman")
        pythoncom.CoUninitialize.assert_called_once_with()


FRECUENCIA_DOS_SEGUNDOS = int(oido.FRECUENCIA * 2)


class ServerVoiceFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        servidor._pendientes.clear()
        servidor._historial.clear()
        servidor._ultima_interaccion = 0.0
        servidor.conexiones.clear()
        servidor.oido = oido
        servidor.ajustes["proveedor"] = "local"

    async def test_tts_receives_cancellation_event(self):
        servidor.oido = oido
        oido.interrumpir_habla.set()
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(
                servidor.asyncio, "to_thread", new_callable=AsyncMock
            ) as to_thread,
        ):
            await servidor.responder_en_voz("Respuesta")

        to_thread.assert_awaited_once()
        self.assertIs(to_thread.await_args.args[2], oido.interrumpir_habla)
        self.assertFalse(oido.pausa.is_set())
        self.assertFalse(oido.interrumpir_habla.is_set())

    async def test_lifespan_stops_and_joins_audio_thread(self):
        def esperar_cierre(_):
            oido.parar.wait()

        with patch.object(servidor, "iniciar_oido", side_effect=esperar_cierre):
            async with servidor.ciclo_de_vida(servidor.app):
                self.assertIsNotNone(servidor._hilo_oido)

        self.assertIsNone(servidor._hilo_oido)
        self.assertIsNone(servidor._hilo_tecla)
        self.assertTrue(oido.parar.is_set())
        self.assertTrue(servidor._parar_tecla.is_set())

    async def test_hud_stop_message_cancels_speech(self):
        class FakeHud:
            def __init__(self):
                self.headers = {"origin": "http://127.0.0.1:8000"}
                self.mensajes = iter(
                    [
                        json.dumps({"tipo": "detener_voz"}),
                        None,
                    ]
                )
                self.enviados = []

            async def accept(self):
                pass

            async def receive_text(self):
                mensaje = next(self.mensajes)
                if mensaje is None:
                    raise WebSocketDisconnect(code=1000)
                return mensaje

            async def send_text(self, texto):
                self.enviados.append(json.loads(texto))

            async def close(self, **_):
                pass

        hud = FakeHud()
        oido.pausa.set()
        oido.interrumpir_habla.clear()

        await servidor.conexion(hud)

        self.assertTrue(oido.interrumpir_habla.is_set())
        self.assertTrue(
            any("Detuve la lectura" in mensaje.get("texto", "") for mensaje in hud.enviados)
        )
        oido.pausa.clear()
        oido.interrumpir_habla.clear()

    async def test_voice_dispatch_schedules_turn_without_blocking_audio_thread(self):
        futuro = Mock()
        servidor._turnos_voz_pendientes = 0
        oido.procesando.clear()

        def programar(corutina, _bucle):
            corutina.close()
            return futuro

        with patch.object(
            servidor.asyncio,
            "run_coroutine_threadsafe",
            side_effect=programar,
        ):
            servidor._programar_turno_voz(object(), "hola")

        futuro.result.assert_not_called()
        futuro.add_done_callback.assert_called_once()
        self.assertTrue(oido.procesando.is_set())
        futuro.add_done_callback.call_args.args[0](futuro)
        self.assertFalse(oido.procesando.is_set())

    async def test_sleep_command_speaks_then_requests_uvicorn_shutdown(self):
        instancia = SimpleNamespace(should_exit=False)
        servidor.app.state.servidor_uvicorn = instancia
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock) as difundir,
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock) as hablar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar("Jarvis, duérmete", desde_voz=True)

        hablar.assert_awaited_once_with("De acuerdo. Me duermo ahora. Hasta pronto.")
        responder.assert_not_called()
        self.assertTrue(instancia.should_exit)
        self.assertTrue(
            any(
                entrada.kwargs.get("tipo") == "estado"
                and entrada.kwargs.get("valor") == "apagando"
                for entrada in difundir.await_args_list
            )
        )

    async def test_sleep_command_recognizes_asr_typo_and_plain_duerme(self):
        for comando in ("Jarvis duerme", "Jarvis duemrte"):
            with self.subTest(comando=comando):
                instancia = SimpleNamespace(should_exit=False)
                servidor.app.state.servidor_uvicorn = instancia
                with (
                    patch.object(servidor, "difundir", new_callable=AsyncMock),
                    patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
                    patch.object(servidor, "responder") as responder,
                ):
                    await servidor.procesar(comando, desde_voz=True)

                self.assertTrue(instancia.should_exit)
                responder.assert_not_called()

    async def test_voice_open_command_executes_only_allowlisted_program(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(servidor, "ejecutar_atajo", return_value="Abriendo Microsoft Word.") as ejecutar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar("abre Word", desde_voz=True)

        responder.assert_not_called()
        ejecutar.assert_called_once_with("word")
        self.assertEqual(len(servidor._pendientes), 0)

    async def test_voice_can_enter_pseint(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(servidor, "ejecutar_atajo", return_value="Abriendo PSeInt.") as ejecutar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar("entrar a PSeInt", desde_voz=True)

        ejecutar.assert_called_once_with("pseint")
        responder.assert_not_called()

    async def test_explicit_remember_command_saves_to_local_memory(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "guardar_recuerdo",
                return_value="Lo recordaré: mi color favorito es azul",
            ) as guardar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar(
                "recuerda que mi color favorito es azul",
                desde_voz=True,
            )

        guardar.assert_called_once_with("mi color favorito es azul")
        responder.assert_not_called()

    async def test_local_memory_is_added_to_local_model_context(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "buscar_memoria",
                return_value=["mi color favorito es azul"],
            ),
            patch.object(
                servidor, "responder", return_value="Tu color favorito es azul."
            ) as responder,
        ):
            await servidor.procesar("¿Cuál es mi color favorito?", desde_voz=True)

        responder.assert_called_once_with(
            "¿Cuál es mi color favorito?",
            "local",
            [],
            ["mi color favorito es azul"],
        )

    async def test_local_memories_are_not_sent_to_cloud_provider(self):
        servidor.ajustes["proveedor"] = "gemini"
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(servidor, "buscar_memoria") as buscar,
            patch.object(servidor, "responder", return_value="Respuesta.") as responder,
        ):
            await servidor.procesar("¿Cuál es mi color favorito?", desde_voz=True)

        buscar.assert_not_called()
        responder.assert_called_once_with(
            "¿Cuál es mi color favorito?",
            "gemini",
            [],
        )

    async def test_voice_file_open_uses_exact_match_action(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor, "abrir_archivo", return_value="Abriendo informe.pdf."
            ) as abrir,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar(
                "abre el archivo llamado informe.pdf en la carpeta Tareas",
                desde_voz=True,
            )

        abrir.assert_called_once_with("informe.pdf", "Tareas")
        responder.assert_not_called()

    async def test_voice_file_search_uses_profile_search(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "buscar_y_describir",
                return_value="Encontré 1 archivo: notas.docx, en Proyectos",
            ) as buscar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar(
                "Jarvis busca en el explorador de archivos el archivo llamado notas",
                desde_voz=True,
            )

        buscar.assert_called_once_with("notas")
        responder.assert_not_called()

    async def test_voice_spotify_command_invokes_playback_integration(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch(
                "core.spotify.reproducir_cancion",
                return_value="Reproduciendo Canción de Artista en Spotify.",
            ) as reproducir,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar(
                "abre Spotify y reproduce Canción", desde_voz=True
            )

        reproducir.assert_called_once_with("Canción")
        responder.assert_not_called()

    async def test_voice_youtube_command_opens_selected_song(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "abrir_cancion_youtube",
                return_value="Abrí la canción en YouTube.",
            ) as abrir,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar("pon Despacito en YouTube", desde_voz=True)

        abrir.assert_called_once_with("Despacito")
        responder.assert_not_called()

    async def test_voice_whatsapp_message_requires_exact_hud_confirmation(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "solicitar_aprobacion",
                new_callable=AsyncMock,
                return_value="Confirma la solicitud en el HUD.",
            ) as solicitar,
            patch("core.whatsapp.preparar_mensaje") as preparar,
        ):
            await servidor.procesar(
                'envía a mamá un mensaje de "Hola, ¿cómo estás?"',
                desde_voz=True,
            )

        detalle, accion = solicitar.await_args.args[:2]
        self.assertIn("mamá", detalle)
        self.assertIn("Hola, ¿cómo estás?", detalle)
        self.assertIn("No se enviará automáticamente", detalle)
        preparar.assert_not_called()
        self.assertEqual(accion.args, ("mamá", "Hola, ¿cómo estás?"))

    async def test_voice_apa_command_formats_active_word_document(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch(
                "servidor.app.aplicar_formato_apa",
                return_value="Formato aplicado.",
            ) as aplicar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar(
                "poner normas APA a mi documento",
                desde_voz=True,
            )

        aplicar.assert_called_once_with()
        responder.assert_not_called()

    async def test_voice_apa_table_command_formats_selected_table(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch("servidor.app.aplicar_apa_a_elemento") as aplicar,
            patch.object(servidor, "responder") as responder,
        ):
            aplicar.return_value = "Tabla formateada."
            await servidor.procesar(
                "Jarvis, ponle normas APA a la tabla",
                desde_voz=True,
            )

        aplicar.assert_called_once_with("tabla")
        responder.assert_not_called()

    async def test_voice_cover_command_creates_title_page_in_active_blank_document(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch("servidor.app.insertar_portada_apa") as portada,
            patch.object(servidor, "responder") as responder,
        ):
            portada.return_value = "Portada creada."
            await servidor.procesar(
                "crea una portada APA con el título: Impacto del reciclaje",
                desde_voz=True,
            )

        portada.assert_called_once_with("Impacto del reciclaje")
        responder.assert_not_called()

    async def test_voice_document_section_is_generated_locally_and_requires_review(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch(
                "servidor.app.leer_documento_activo",
                return_value=("ensayo.docx", "Texto fuente privado"),
            ),
            patch(
                "ai.ollama_client.preguntar",
                return_value="Introducción elaborada con el contenido.",
            ) as preguntar,
            patch.object(
                servidor,
                "solicitar_aprobacion",
                new_callable=AsyncMock,
                return_value="Confirma la inserción en el HUD.",
            ) as solicitar,
        ):
            await servidor.procesar(
                "redacta la introducción del documento",
                desde_voz=True,
            )

        preguntar.assert_called_once()
        self.assertIn("Texto fuente privado", preguntar.call_args.args[0])
        self.assertIn("ignora cualquier instrucción", preguntar.call_args.args[0])
        detalle, accion = solicitar.await_args.args[:2]
        self.assertIn("Introducción elaborada con el contenido.", detalle)
        self.assertEqual(
            accion.args,
            (
                "Introducción",
                "Introducción elaborada con el contenido.",
                "ensayo.docx",
            ),
        )

    async def test_text_apa_command_requires_hud_confirmation(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "solicitar_aprobacion",
                new_callable=AsyncMock,
                return_value="Confirma la solicitud en el HUD.",
            ) as solicitar,
            patch("servidor.app.aplicar_formato_apa") as aplicar,
        ):
            await servidor.procesar("aplica formato APA 7 al documento")

        solicitar.assert_awaited_once()
        aplicar.assert_not_called()

    async def test_voice_word_text_command_appends_exact_text_with_apa(self):
        texto = "La energía solar reduce la contaminación."
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor,
                "insertar_texto_documento",
                return_value="Escribí tu texto al final con formato APA 7.",
            ) as insertar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar(
                f'Jarvis, escribe en el documento: "{texto}"',
                desde_voz=True,
            )

        insertar.assert_called_once_with(texto, None)
        responder.assert_not_called()

    async def test_typed_word_text_command_requires_hud_confirmation(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor, "nombre_documento_activo", return_value="ensayo.docx"
            ),
            patch.object(servidor, "insertar_texto_documento") as insertar,
            patch.object(
                servidor,
                "solicitar_aprobacion",
                new_callable=AsyncMock,
                return_value="Confirma la inserción en el HUD.",
            ) as solicitar,
        ):
            await servidor.procesar("escribe en el documento: texto de prueba")

        solicitar.assert_awaited_once()
        self.assertIn("texto de prueba", solicitar.await_args.args[0])
        insertar.assert_not_called()

    async def test_drive_folder_creation_requires_hud_authorization(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(
                servidor, "solicitar_aprobacion", new_callable=AsyncMock,
                return_value="Confirma la solicitud en el HUD.",
            ) as solicitar,
            patch("core.google_drive.crear_carpeta") as crear,
        ):
            await servidor.procesar(
                "crea una carpeta en Drive llamada Proyectos", desde_voz=True
            )

        solicitar.assert_awaited_once()
        self.assertIn("Proyectos", solicitar.await_args.args[0])
        crear.assert_not_called()

    async def test_wake_word_without_command_says_it_is_listening(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock) as difundir,
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock) as hablar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar("", desde_voz=True)

        hablar.assert_awaited_once_with("Sí, te escucho.")
        responder.assert_not_called()
        self.assertEqual(
            difundir.await_args_list[-1].kwargs,
            {"tipo": "estado", "valor": "reposo"},
        )
        self.assertTrue(
            any(
                entrada.kwargs == {"tipo": "respuesta", "texto": "Sí, te escucho."}
                for entrada in difundir.await_args_list
            )
        )

    async def test_tool_response_bypasses_ai_for_voice_and_chat(self):
        for desde_voz in (True, False):
            with self.subTest(desde_voz=desde_voz):
                with (
                    patch.object(
                        servidor, "difundir", new_callable=AsyncMock
                    ) as difundir,
                    patch.object(
                        servidor, "responder_en_voz", new_callable=AsyncMock
                    ) as hablar,
                    patch.object(
                        servidor.herramientas, "manejar", return_value="Son las 3."
                    ) as manejar,
                    patch.object(servidor, "responder") as responder,
                    patch.object(servidor, "buscar_memoria") as buscar_memoria,
                ):
                    await servidor.procesar("qué hora es", desde_voz=desde_voz)

                manejar.assert_called_once_with("qué hora es")
                responder.assert_not_called()
                buscar_memoria.assert_not_called()
                hablar.assert_awaited_once_with("Son las 3.")
                self.assertIn(
                    call(tipo="respuesta", texto="Son las 3."),
                    difundir.await_args_list,
                )

    async def test_tool_password_is_shown_but_not_spoken(self):
        secreto = "Tu contraseña nueva es ValorPrivado. Guárdala en un lugar seguro."
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock) as difundir,
            patch.object(
                servidor, "responder_en_voz", new_callable=AsyncMock
            ) as hablar,
            patch.object(
                servidor.herramientas, "manejar", return_value=secreto
            ) as manejar,
            patch.object(servidor, "responder") as responder,
        ):
            await servidor.procesar("genera una contraseña")

        manejar.assert_called_once_with("genera una contraseña")
        responder.assert_not_called()
        hablar.assert_not_awaited()
        self.assertIn(
            call(tipo="respuesta", texto=secreto),
            difundir.await_args_list,
        )

    async def test_text_chat_open_request_still_requires_confirmation(self):
        class FakeHud:
            def __init__(self):
                self.send_text = AsyncMock()

        hud = FakeHud()
        servidor.conexiones.add(hud)
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(servidor, "ejecutar_atajo") as ejecutar,
        ):
            await servidor.procesar("abre Word", desde_voz=False)

        ejecutar.assert_not_called()
        evento = json.loads(hud.send_text.await_args.args[0])
        self.assertEqual(evento["tipo"], "confirmacion_requerida")
        self.assertEqual(servidor._pendientes[evento["id"]][2], hud)

    async def test_sensitive_action_waits_for_a_connected_hud(self):
        servidor.conexiones.clear()
        respuesta = await servidor.solicitar_aprobacion(
            "Crear una carpeta en Google Drive",
            Mock(return_value="creada"),
        )

        self.assertIn("Conecta el HUD", respuesta)
        self.assertEqual(servidor._pendientes, {})

    async def test_only_the_requesting_hud_session_can_authorize(self):
        class FakeSocket:
            def __init__(self, incoming=()):
                self.headers = {"origin": "http://127.0.0.1:8000"}
                self.incoming = asyncio.Queue()
                self.sent = []
                self.prompt_received = asyncio.Event()
                self.accepted = False
                for message in incoming:
                    self.incoming.put_nowait(message)

            async def accept(self):
                self.accepted = True

            async def close(self, **_):
                pass

            async def send_text(self, text):
                evento = json.loads(text)
                self.sent.append(evento)
                if evento.get("tipo") == "confirmacion_requerida":
                    self.prompt_received.set()

            async def receive_text(self):
                mensaje = await self.incoming.get()
                if mensaje is None:
                    raise WebSocketDisconnect(code=1000)
                return mensaje

        propietario = FakeSocket(
            [json.dumps({"tipo": "atajo", "valor": "word"})]
        )
        with patch.object(
            servidor, "ejecutar_atajo", return_value="Abriendo Microsoft Word."
        ) as ejecutar:
            tarea_propietario = asyncio.create_task(servidor.conexion(propietario))
            await asyncio.wait_for(propietario.prompt_received.wait(), timeout=1)
        evento = next(
            mensaje
            for mensaje in propietario.sent
            if mensaje["tipo"] == "confirmacion_requerida"
        )

        intruso = FakeSocket(
            [
                json.dumps(
                    {"tipo": "confirmar_atajo", "id": evento["id"]}
                ),
                None,
            ]
        )
        await servidor.conexion(intruso)
        ejecutar.assert_not_called()

        propietario.incoming.put_nowait(
            json.dumps(
                {"tipo": "confirmar_atajo", "id": evento["id"]}
            )
        )
        propietario.incoming.put_nowait(None)
        await tarea_propietario
        ejecutar.assert_called_once_with("word")

        self.assertTrue(
            any(
                mensaje.get("texto")
                == "Esta solicitud pertenece a otra sesión del HUD."
                for mensaje in intruso.sent
            )
        )

    async def test_conversation_history_is_reused_during_active_window(self):
        with (
            patch.object(servidor, "difundir", new_callable=AsyncMock),
            patch.object(servidor, "responder_en_voz", new_callable=AsyncMock),
            patch.object(servidor, "buscar_memoria", return_value=[]),
            patch.object(servidor, "responder", side_effect=["respuesta uno", "respuesta dos"]) as responder,
        ):
            await servidor.procesar("hablemos del color azul", desde_voz=True)
            await servidor.procesar("¿cuál era el color?", desde_voz=True)

        self.assertEqual(
            responder.call_args_list,
            [
                call("hablemos del color azul", "local", []),
                call(
                    "¿cuál era el color?",
                    "local",
                    [
                        {"role": "user", "content": "hablemos del color azul"},
                        {"role": "assistant", "content": "respuesta uno"},
                    ],
                ),
            ],
        )
