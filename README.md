# Jarvis

Asistente personal local en Python, con interfaz web servida por FastAPI y comunicación por WebSocket. La interacción principal es la voz; el chat del HUD es secundario.

## Ejecutar

1. Activa el entorno virtual (Python 3.12) e instala las dependencias:

```
   pip install -r requirements.txt
   pip install resemblyzer==0.1.4 --no-deps
```

   Resemblyzer se instala aparte con `--no-deps` porque, en Windows, una de sus dependencias intenta compilarse y suele fallar; las que sí necesita ya están en `requirements.txt`. El archivo `requirements-lock.txt` guarda las versiones exactas con las que Jarvis funcionó y sirve solo como referencia, no para instalar.
2. Registra tu voz con `python registrar_voz.py` (ocho frases cortas, en un lugar silencioso y con el micrófono que vas a usar). Después comprueba el oído con `python diagnostico_oido.py`.
3. Inicia Jarvis con `python main.py`; el servidor abre el HUD en `127.0.0.1:8000`.
4. El proveedor local requiere Ollama con `llama3.2:3b`. Gemini necesita `GEMINI_API_KEY` en `.env`.

Di «Jarvis» seguido de una orden. Después de una orden reconocida, Jarvis acepta turnos siguientes sin repetir la palabra clave durante 20 segundos. Las conversaciones conservan hasta ocho mensajes previos mientras el turno anterior siga dentro de esa ventana. El indicador del HUD muestra el estado del micrófono y del asistente. Desactivar TTS silencia las respuestas, pero no deshabilita el micrófono.

## HUD y escucha por voz

El HUD oficial muestra CPU, RAM, uso del disco, batería, temperatura, tráfico de red, reloj y fecha. La temperatura indica «N/D» si Windows no ofrece sensores compatibles; la velocidad de red se calcula localmente a partir del tráfico total del equipo. El micrófono se mantiene abierto en el servidor en el modo de escucha predeterminado.

El panel incluye control multimedia del reproductor activo, búsqueda web/archivos y calendario, tareas y notas. Tareas, notas y eventos se guardan en el almacenamiento local del navegador y no se sincronizan con Windows, Ollama ni otros dispositivos. El calendario es una vista local; no está conectado a Google Calendar. El chat es un canal secundario: puedes dar las mismas órdenes por voz o escribirlas. Los accesos del HUD abren directamente las aplicaciones permitidas por `core/acciones.py`; las acciones sensibles (por ejemplo, Drive y WhatsApp) conservan su confirmación.

El control de brillo usa la interfaz WMI de Windows y solo funciona con monitores que expongan ajuste de brillo; si no está disponible, Jarvis lo indica. Los accesos web abren su sitio en otra pestaña.

No hace falta pulsar un botón de grabación: di «Jarvis» seguido de tu solicitud. El HUD muestra el estado del micrófono del servidor; **Respuesta hablada** solo activa o silencia el TTS y no detiene la escucha. Mientras Jarvis habla, decir «Jarvis» intenta cancelar la síntesis y permite dar otra orden. Para una interrupción inmediata, pulsa **F8** desde cualquier aplicación o el botón **DETENER** del HUD. Estos controles solo silencian a Jarvis; no autorizan ni ejecutan órdenes. Las órdenes de voz siguen requiriendo que Resemblyzer autorice tu voz. Whisper puede equivocarse con ruido, eco o micrófonos lejanos.

## Voz, verificación y privacidad

Cada segmento se compara con la huella local de Resemblyzer antes de enviarse a Whisper o al modelo. Las órdenes solo se ejecutan si la voz supera esa comprobación y la frase empieza con «Jarvis» (durante 20 segundos tras una orden reconocida se pueden continuar solicitudes sin repetir la palabra de activación). Si no hay huella registrada, la escucha no se habilita. El audio se normaliza para la transcripción después de comprobar la huella, no antes.

La similitud de voz no equivale a autenticación biométrica infalible: puede rechazar al propietario por ruido o aceptar una grabación reproducida de una voz autorizada. No autorices operaciones destructivas o que compartan datos basándote únicamente en esta verificación. Mantén `voz/mi_voz.npy` y `.env` privados.

## Configurar reconocimiento y memoria local

Jarvis muestra en la terminal el nombre del micrófono elegido y el tamaño/configuración de Whisper. Para fijar un micrófono concreto, copia su nombre o número de entrada desde la lista de dispositivos de Windows y añade una de estas líneas a `.env`:

```dotenv
JARVIS_MIC_DEVICE=USB Microphone
```

También puedes usar el número que Jarvis imprime como `entrada N`:

```dotenv
JARVIS_MIC_DEVICE=2
```

Si no defines esta opción, se usa el micrófono predeterminado de Windows. Si el valor escrito no coincide, Jarvis informa los micrófonos disponibles en vez de cambiar silenciosamente a otro.

Whisper usa `small`, CPU e `int8` de forma predeterminada. En equipos lentos puedes probar `JARVIS_WHISPER_MODEL=base` o `tiny` y reducir `JARVIS_WHISPER_BEAM_SIZE` a `3`; responderá con menos carga, aunque los modelos más pequeños pueden transcribir peor. Los tamaños permitidos son `tiny`, `base`, `small`, `medium` y `large-v3`; el valor predeterminado de búsqueda es 5. Si tienes una GPU NVIDIA compatible con CUDA, puedes probar `JARVIS_WHISPER_DEVICE=cuda` y `JARVIS_WHISPER_COMPUTE_TYPE=float16`; si no funciona, quita esas líneas para volver a CPU.

Los recuerdos son optativos y solo se guardan cuando dices o escribes «recuerda que mi color favorito es azul». Pregunta «¿qué recuerdas de mi color favorito?» o «muéstrame mis recuerdos» para consultarlos; di «olvida mi color favorito es azul» para borrar una coincidencia exacta. Se guardan en una base SQLite local en `%LOCALAPPDATA%\Jarvis\memoria.sqlite3`, no se suben a Drive ni se envían a Gemini. Cuando el proveedor activo es Ollama local, los recuerdos que coinciden con la pregunta se pueden incluir como contexto; al usar Gemini no se busca ni se adjunta esa memoria.

OpenJarvis organiza funciones como voz, motores locales, herramientas, memoria y evaluaciones en componentes separados. Jarvis adopta esa organización en pequeño y conserva sus propias funciones, su interfaz y Ollama/Gemini; no instala ni copia el framework entero.

## Micrófono, candado de voz y diagnóstico

Jarvis usa el micrófono predeterminado de Windows. Si tienes un micrófono externo, conéctalo y elige su número con esta orden (aparece cada dispositivo de entrada con su tipo de conexión; en general conviene uno marcado como MME):

```
python -c "import sounddevice as sd; [print(i, d['name'], '|', sd.query_hostapis(d['hostapi'])['name']) for i, d in enumerate(sd.query_devices()) if d['max_input_channels'] > 0]"
```

Luego añade el número a `.env` (por ejemplo `JARVIS_MIC_DEVICE=3`). **Cada vez que cambies de micrófono, vuelve a ejecutar `python registrar_voz.py`**, porque la huella de tu voz depende del micrófono con el que se grabó.

`registrar_voz.py` guarda el promedio de ocho frases y calcula un umbral propio, que se guarda en `voz/mi_voz_umbral.json` (fuera de Git). Para ajustarlo a mano usa `JARVIS_UMBRAL_VOZ=0.70` en `.env`. `diagnostico_oido.py` graba tres pruebas y muestra, en cada una, el volumen, el parecido con tu voz, lo que entendió Whisper y si detectó la palabra «Jarvis».

Solo para pruebas puedes desactivar el candado con `JARVIS_VERIFICAR_VOZ=0`; con eso Jarvis obedece a cualquier voz, así que quita esa línea al terminar.

## Voz de Jarvis (tres motores)

`voz/hablar.py` puede hablar con tres voces, elegidas con `JARVIS_VOZ` en `.env`:

- `windows` (predeterminada): voz de Windows, sin internet. Se puede elegir con `JARVIS_VOZ_WINDOWS=Helena`.
- `piper`: voz neuronal local, sin internet. Descarga una voz una sola vez (necesita internet) y se guarda fuera del repositorio:

  ```
  python -m piper.download_voices es_ES-davefx-medium --download-dir "$env:LOCALAPPDATA\Jarvis\voces"
  ```

  Otra voz se elige con `JARVIS_VOZ_PIPER=nombre`; `python -m piper.download_voices` lista las disponibles. Revisa la licencia de cada voz antes de redistribuirla.
- `edge`: voz natural en línea mediante `edge-tts`, un servicio de Microsoft no oficial que puede dejar de funcionar. Se elige con `JARVIS_VOZ_EDGE=es-CO-GonzaloNeural`; `python -m edge_tts --list-voices` muestra las demás.
- `auto`: usa `edge` si hay internet, si no `piper`, y si falla usa `windows`.

Si un motor falla, Jarvis lo avisa en la terminal y usa el siguiente.

## Acciones y apagado

- «Jarvis, abre Word/VS Code/PSeInt/WhatsApp/Spotify/Roblox/Drive/correo» —o «Jarvis, entrar a PSeInt»— solo reconoce destinos fijos de `core/acciones.py`. Word, VS Code y PSeInt se resuelven desde sus ubicaciones habituales de instalación; las órdenes de voz autenticadas y los accesos del HUD abren directamente esos destinos permitidos. El texto del modelo nunca se ejecuta como comando. Las acciones sensibles como Drive y WhatsApp mantienen sus confirmaciones.
- «Jarvis, busca en el explorador de archivos un archivo/documento llamado informe» busca por nombre (primero en el índice de Windows Search y luego en tu perfil, Escritorio, Documentos, Descargas y OneDrive), sin leer el contenido. Omite carpetas de sistema y caché y devuelve como máximo ocho coincidencias. «Jarvis, abre el archivo/documento llamado informe.pdf» solo abre una coincidencia exacta. Si el nombre no es único, indica la carpeta, por ejemplo: «abre el documento llamado informe.pdf en la carpeta Tareas».
- «Jarvis, abre Spotify y reproduce [canción]» o «Jarvis, reproduce [canción] en Spotify» funciona sin configurar una API: Jarvis abre la búsqueda para que elijas la canción en Spotify. No cuesta, pero con una cuenta gratis tendrás que iniciar la reproducción tú; la API oficial para reproducir automáticamente requiere Premium. Si ya tienes Premium y configuras `JARVIS_SPOTIFY_CLIENT_ID` y autorizas la aplicación, Jarvis intenta reproducirla directamente. «Jarvis, abre Spotify y busca [canción]» también abre la búsqueda.
- Con Word abierto y el documento correcto activo, di «Jarvis, poner normas APA a mi documento» o «Jarvis, aplica formato APA 7 al documento». Jarvis usa Word COM mediante `pywin32`, cambia papel carta, márgenes de una pulgada, Times New Roman de 12 puntos, doble espacio, alineación izquierda, sangría inicial de media pulgada y numeración de página; no guarda automáticamente.
- Después puedes decir «Jarvis, escribe en el documento: [tu texto]», «Jarvis, pon en el documento el siguiente texto: [tu texto]» o «Jarvis, pon [tu texto] en el documento de Word». Jarvis añade el texto dictado al final del documento activo y le aplica Times New Roman 12, doble espacio y sangría APA; no guarda automáticamente. Si dictas por voz, abre el documento correcto antes de dar la orden. Si escribes la orden en el chat, autorízala en el HUD.
- Para tablas/figuras, selecciona una celda de la tabla o la imagen y di «Jarvis, ponle normas APA a la tabla» o «Jarvis, aplica normas APA a esta imagen». Jarvis ajusta el estilo básico de la tabla o centra y limita el ancho de la imagen; añade o revisa manualmente el número, título y nota APA.
- Para una portada en un documento vacío, di «Jarvis, crea una portada APA con el título: Impacto del reciclaje». La portada incluye campos para estudiante, institución, curso, docente y fecha, y deja un salto de página para comenzar el trabajo. Completa los campos entre corchetes.
- Para pedir una sección basada en el documento abierto, di «Jarvis, redacta la introducción», «Jarvis, crea los objetivos» o «Jarvis, genera las conclusiones». Jarvis lee el texto del documento activo, lo procesa solo con Ollama local y te presenta el borrador en el HUD para que confirmes antes de insertarlo al final. Revisa el contenido generado y guarda los cambios tú.
- «Jarvis, pon música en YouTube», por ejemplo «Jarvis, pon [canción] en YouTube», busca el primer resultado público sin usar una API de pago ni descargar el audio, y abre su página con reproducción automática solicitada. YouTube gratuito puede mostrar anuncios y el navegador puede exigir un clic para iniciar el sonido; si ocurre, pulsa Reproducir.
- «Jarvis, envía a [nombre tal como está guardado en WhatsApp] un mensaje de “Hola”», por ejemplo «envía a Carlos Pérez un mensaje que diga Llego en 10 minutos», muestra en el HUD el destinatario y el texto exactos para autorizar. Tras aprobar, Jarvis abre el enlace oficial de WhatsApp con el texto precargado; selecciona el contacto correcto cuando WhatsApp lo solicite y pulsa Enviar. Jarvis no lee tu agenda ni envía el mensaje por sí solo.
- Gmail y Drive se abren en el navegador predeterminado de Windows mediante `os.startfile` con direcciones HTTPS fijas; no se envían credenciales desde Jarvis al navegador.
- «Jarvis, abre Gmail», «Jarvis, abre el correo Gmail» y «Jarvis, abre mi correo de Gmail» abren Gmail en el navegador. «Abre correo» sin especificar Gmail conserva Outlook como destino.
- Las operaciones de Google Drive requieren conexión a Internet y consentimiento OAuth. En Google Cloud Console habilita **Google Drive API**, configura la pantalla de consentimiento OAuth (en modo de prueba, añade tu cuenta como usuario de prueba) y crea un cliente OAuth de tipo **Aplicación de escritorio**. Guarda su JSON como `secrets/google_oauth_client.json` o indica otra ruta en `JARVIS_GOOGLE_OAUTH_CLIENT`. «Jarvis, crea una carpeta en Drive llamada Proyectos» y «Jarvis, sube a Drive el archivo informe.pdf» muestran primero una solicitud de permiso en el HUD. La subida solo permite archivos ubicados en Escritorio, Documentos, Descargas o OneDrive, de hasta 50 MB; no acepta otros archivos del perfil ni del sistema. El alcance OAuth es `drive.file`. Las credenciales se excluyen de Git y los tokens se guardan en `%LOCALAPPDATA%\Jarvis`, fuera del repositorio. Revoca el acceso desde tu cuenta de Google si ya no deseas que Jarvis opere con Drive.
- Una subida con nombres repetidos requiere especificar la carpeta local, por ejemplo: «sube a Drive el archivo informe.pdf en la carpeta Tareas». Las confirmaciones del HUD son de un solo uso, vencen en 30 segundos y solo las puede aceptar la sesión que las solicitó.
- «Jarvis, duérmete», «Jarvis, duerme» y la transcripción frecuente «Jarvis, duemrte» responden y apagan Uvicorn y los hilos de audio. El HUD evita reconectarse y sale de la página de Jarvis al quedar apagado. Usa `python main.py` para que el apagado controlado esté disponible.
- El widget del clima usa la ciudad configurada por `JARVIS_CIUDAD` en `.env` (Ibagué por defecto) y consulta Open-Meteo al pulsar **Actualizar**; no solicita ni envía la ubicación GPS del navegador. Abrir Gmail lleva a su sitio web; Jarvis todavía no redacta ni envía correos.
- El servidor se limita a loopback y el WebSocket acepta los orígenes locales conocidos. No expongas Jarvis a otros dispositivos sin autenticación y protección de transporte.