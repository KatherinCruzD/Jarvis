import unittest
from unittest.mock import Mock, patch

from core import herramientas, internet, utilidades


class HerramientasTests(unittest.TestCase):
    def tearDown(self):
        utilidades._pendiente.update({"accion": None, "hasta": 0.0})

    def test_responde_la_hora_sin_consultar_la_red(self):
        with patch.object(internet, "manejar", return_value=None):
            respuesta = herramientas.manejar("qué hora es")

        self.assertRegex(respuesta, r"^(?:Es la|Son las) \d{1,2}:\d{2}")

    def test_calcula_operacion_en_espanol(self):
        respuesta = herramientas.manejar("cuánto es 2 más 2")

        self.assertEqual(respuesta, "El resultado es 4.")

    def test_genera_contrasena_nueva(self):
        with patch.object(
            utilidades, "generar_contrasena", return_value="ClavePrueba123!"
        ):
            respuesta = herramientas.manejar("genera una contraseña")

        self.assertEqual(
            respuesta,
            "Tu contraseña nueva es ClavePrueba123!. Guárdala en un lugar seguro.",
        )

    def test_consulta_clima_con_respuestas_http_simuladas(self):
        geocodificacion = Mock()
        geocodificacion.json.return_value = {
            "results": [{"name": "Ibagué", "latitude": 4.4, "longitude": -75.2}]
        }
        pronostico = Mock()
        pronostico.json.return_value = {
            "current": {"temperature_2m": 20, "weather_code": 1},
            "daily": {"temperature_2m_max": [25], "temperature_2m_min": [15]},
        }

        with patch.object(
            internet.requests, "get", side_effect=[geocodificacion, pronostico]
        ) as obtener:
            respuesta = herramientas.manejar("qué clima hace")

        self.assertIn("En Ibagué hay 20 grados", respuesta)
        self.assertEqual(obtener.call_count, 2)

    def test_consulta_wikipedia_con_respuestas_http_simuladas(self):
        busqueda = Mock()
        busqueda.json.return_value = ["Ada Lovelace", ["Ada Lovelace"], [], []]
        resumen = Mock()
        resumen.json.return_value = {
            "extract": "Ada Lovelace fue una matemática inglesa."
        }

        with patch.object(
            internet.requests, "get", side_effect=[busqueda, resumen]
        ) as obtener:
            respuesta = herramientas.manejar("busca en wikipedia Ada Lovelace")

        self.assertEqual(respuesta, "Ada Lovelace fue una matemática inglesa.")
        self.assertEqual(obtener.call_count, 2)

    def test_consulta_divisa_con_respuesta_http_simulada(self):
        tasas = Mock()
        tasas.json.return_value = {"rates": {"COP": 4000, "USD": 1}}

        with patch.object(internet.requests, "get", return_value=tasas) as obtener:
            respuesta = herramientas.manejar("cuánto vale el dólar")

        self.assertIn("4.000 pesos colombianos", respuesta)
        obtener.assert_called_once()

    def test_consulta_noticias_con_contenido_http_simulado(self):
        respuesta_http = Mock()
        respuesta_http.content = (
            b"<rss><channel><item><title>Noticia de prueba</title>"
            b"</item></channel></rss>"
        )

        with patch.object(
            internet.requests, "get", return_value=respuesta_http
        ) as obtener:
            respuesta = herramientas.manejar("dime las noticias")

        self.assertIn("Noticia de prueba", respuesta)
        obtener.assert_called_once()

    def test_busqueda_google_no_abre_un_navegador_real(self):
        with patch.object(internet.webbrowser, "open") as abrir:
            respuesta = herramientas.manejar("busca Jarvis en Google")

        self.assertEqual(respuesta, "Buscando jarvis en Google.")
        abrir.assert_called_once()

    def test_apagar_y_reiniciar_solo_se_ejecutan_con_run_simulado(self):
        with patch.object(utilidades.subprocess, "run") as ejecutar:
            for orden, bandera in (
                ("apaga el computador", "/s"),
                ("reinicia el computador", "/r"),
            ):
                with self.subTest(orden=orden):
                    respuesta_confirmacion = herramientas.manejar(orden)
                    self.assertIn("Di «confirmo»", respuesta_confirmacion)

                    respuesta_final = herramientas.manejar("confirmo")

                    self.assertIn("en 30 segundos", respuesta_final)
                    ejecutar.assert_called_with(
                        ["shutdown", bandera, "/t", "30"], check=False
                    )
            self.assertEqual(ejecutar.call_count, 2)


if __name__ == "__main__":
    unittest.main()
