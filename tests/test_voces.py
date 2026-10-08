import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import voces
from voz import hablar


class VocesTests(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        base = Path(self.carpeta.name)
        self.parches = [
            patch.object(hablar, "CARPETA_JARVIS", base),
            patch.object(hablar, "CARPETA_VOCES", base / "voces"),
            patch.object(hablar, "ARCHIVO_PREFERENCIA", base / "voz.json"),
            patch.dict(os.environ, {"JARVIS_VOZ": "windows"}),
        ]
        for parche in self.parches:
            parche.start()

    def tearDown(self):
        for parche in self.parches:
            parche.stop()
        self.carpeta.cleanup()

    def _crear_voz_local(self):
        (hablar.CARPETA_VOCES).mkdir(parents=True, exist_ok=True)
        (hablar.CARPETA_VOCES / f"{hablar.PIPER_PREDETERMINADA}.onnx").write_bytes(b"x")

    def test_por_defecto_usa_la_voz_de_windows(self):
        self.assertEqual(hablar.motor_preferido(), "windows")

    def test_cambia_a_la_voz_de_internet_y_la_recuerda(self):
        respuesta = voces.manejar("Jarvis, cambia la voz a la de internet")
        self.assertIn("internet", respuesta)
        self.assertEqual(hablar.motor_preferido(), "edge")

    def test_voz_local_pide_descargarla_si_falta(self):
        respuesta = voces.manejar("usa la voz local")
        self.assertIn("no está descargada", respuesta)
        self.assertEqual(hablar.motor_preferido(), "windows")

    def test_voz_local_se_activa_si_esta_descargada(self):
        self._crear_voz_local()
        voces.manejar("pon la voz neuronal")
        self.assertEqual(hablar.motor_preferido(), "piper")

    def test_vuelve_a_la_voz_de_windows_y_a_la_automatica(self):
        hablar.elegir_motor("edge")
        voces.manejar("cambia a la voz de windows")
        self.assertEqual(hablar.motor_preferido(), "windows")
        voces.manejar("activa la voz automática")
        self.assertEqual(hablar.motor_preferido(), "auto")

    def test_informa_que_voz_usa(self):
        respuesta = voces.manejar("¿qué voz estás usando?")
        self.assertIn("Windows", respuesta)

    def test_ignora_frases_que_no_hablan_de_la_voz(self):
        self.assertIsNone(voces.manejar("qué hora es"))
        self.assertIsNone(voces.manejar("abre word"))
        self.assertIsNone(voces.manejar("tengo la voz ronca"))

    def test_la_orden_de_detener_no_cambia_de_motor(self):
        self.assertEqual(hablar._motores(self._evento_puesto()), ["windows"])

    def _evento_puesto(self):
        import threading

        evento = threading.Event()
        evento.set()
        return evento

    def test_modo_auto_sin_internet_usa_piper_y_luego_windows(self):
        hablar.elegir_motor("auto")
        with patch.object(hablar, "_hay_internet", return_value=False):
            self.assertEqual(hablar._motores(None), ["piper", "windows"])
        with patch.object(hablar, "_hay_internet", return_value=True):
            self.assertEqual(hablar._motores(None), ["edge", "piper", "windows"])


if __name__ == "__main__":
    unittest.main()