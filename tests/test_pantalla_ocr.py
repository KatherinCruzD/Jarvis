import os
import unittest
from unittest.mock import patch

from core.pantalla import consultas, ocr


class OcrTests(unittest.TestCase):
    def test_se_puede_apagar_el_ocr(self):
        with patch.dict(os.environ, {"JARVIS_OCR": "0"}):
            self.assertEqual(ocr.leer(b"png"), ("", ""))

    def test_una_imagen_invalida_no_rompe_a_jarvis(self):
        with patch.dict(os.environ, {"JARVIS_OCR": "1"}):
            self.assertEqual(ocr.leer_texto(b"esto no es una imagen"), "")


class FlujoTests(unittest.TestCase):
    def _manejar(self, leido, proveedor="local"):
        with patch.dict(os.environ, {"JARVIS_VISION": proveedor}), patch.object(
            consultas.captura, "capturar", return_value=(b"png", "la ventana «Word»")
        ), patch.object(consultas.ocr, "leer_texto", return_value=leido) as lector, patch.object(
            consultas.vision, "analizar_texto", return_value="Respuesta con texto."
        ) as con_texto, patch.object(
            consultas.vision, "analizar", return_value="Respuesta con imagen."
        ) as con_imagen:
            respuesta = consultas.manejar("explícame esta ventana")
        return respuesta, lector, con_texto, con_imagen

    def test_con_suficiente_texto_responde_el_modelo_de_texto(self):
        respuesta, _, con_texto, con_imagen = self._manejar("palabra " * 30)
        self.assertEqual(respuesta, "Respuesta con texto.")
        con_texto.assert_called_once()
        con_imagen.assert_not_called()

    def test_con_poco_texto_usa_el_modelo_de_vision(self):
        respuesta, _, con_texto, con_imagen = self._manejar("hola")
        self.assertEqual(respuesta, "Respuesta con imagen.")
        con_texto.assert_not_called()
        con_imagen.assert_called_once()

    def test_con_gemini_no_se_envia_el_texto_leido_por_ocr(self):
        respuesta, lector, con_texto, _ = self._manejar("palabra " * 30, proveedor="gemini")
        lector.assert_not_called()
        con_texto.assert_not_called()
        self.assertIn("en la nube", respuesta)


if __name__ == "__main__":
    unittest.main()