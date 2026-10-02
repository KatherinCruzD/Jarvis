const canvas = document.getElementById("nucleo");
const ctx = canvas.getContext("2d");
const estadoVisual = document.getElementById("estado");
const chat = document.getElementById("chat");
const caja = document.getElementById("caja");
const dialogo = document.getElementById("dialogo-confirmacion");
const conexionIndicador = document.getElementById("conexion-indicador");
const conexionTexto = document.getElementById("conexion-texto");
const actividadVoz = document.getElementById("actividad-voz");

let ancho = 0;
let alto = 0;
let escala = 1;
let socket;
let accionPendiente = null;
let estado = "reposo";
let angulo = 0;
let pulso = 0;
let apagando = false;

const TOTAL = 760;
const puntos = [];
for (let i = 0; i < TOTAL; i++) {
  const y = 1 - (i / (TOTAL - 1)) * 2;
  const radio = Math.sqrt(1 - y * y);
  const theta = i * Math.PI * (3 - Math.sqrt(5));
  puntos.push({ x: Math.cos(theta) * radio, y, z: Math.sin(theta) * radio });
}

const ESTADOS = {
  reposo: { velocidad: 0.0016, amplitud: 0.012, color: "57, 207, 244", etiqueta: "SISTEMAS EN ESPERA" },
  escuchando: { velocidad: 0.006, amplitud: 0.065, color: "113, 255, 197", etiqueta: "ESCUCHANDO" },
  pensando: { velocidad: 0.012, amplitud: 0.035, color: "255, 190, 92", etiqueta: "PROCESANDO SOLICITUD" },
  hablando: { velocidad: 0.004, amplitud: 0.085, color: "87, 204, 255", etiqueta: "RESPONDIENDO" },
};

function ajustarCanvas() {
  escala = Math.min(window.devicePixelRatio || 1, 2);
  ancho = window.innerWidth;
  alto = window.innerHeight;
  canvas.width = Math.round(ancho * escala);
  canvas.height = Math.round(alto * escala);
  ctx.setTransform(escala, 0, 0, escala, 0, 0);
}

window.addEventListener("resize", ajustarCanvas);
ajustarCanvas();

function dibujarNucleo() {
  const actual = ESTADOS[estado] || ESTADOS.reposo;
  const cx = ancho * 0.5;
  const cy =
    ancho <= 790
      ? 82 + Math.min(alto * 0.275, 200)
      : alto * 0.53;
  const base = Math.min(ancho, alto) * (ancho <= 790 ? 0.245 : 0.22);
  const radio = base * (1 + Math.sin(pulso) * actual.amplitud);
  const giroY = Math.cos(angulo);
  const giroZ = Math.sin(angulo);
  const giroX = Math.cos(angulo * 0.62);
  const elevacion = Math.sin(angulo * 0.62);
  const proyectados = [];

  ctx.clearRect(0, 0, ancho, alto);
  angulo += actual.velocidad;
  pulso += 0.035;

  const halo = ctx.createRadialGradient(cx, cy, radio * 0.12, cx, cy, radio * 1.55);
  halo.addColorStop(0, `rgba(${actual.color}, 0.075)`);
  halo.addColorStop(0.62, `rgba(${actual.color}, 0.025)`);
  halo.addColorStop(1, `rgba(${actual.color}, 0)`);
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(cx, cy, radio * 1.55, 0, Math.PI * 2);
  ctx.fill();

  for (const punto of puntos) {
    const x = punto.x * giroY - punto.z * giroZ;
    const z = punto.x * giroZ + punto.z * giroY;
    const y = punto.y * giroX - z * elevacion;
    const profundidad = (punto.y * elevacion + z * giroX + 1) / 2;
    proyectados.push({ x: cx + x * radio, y: cy + y * radio, profundidad });
  }

  proyectados.sort((a, b) => a.profundidad - b.profundidad);
  for (const punto of proyectados) {
    const brillo = 0.15 + punto.profundidad * 0.8;
    const tamano = 0.45 + punto.profundidad * 1.45;
    ctx.beginPath();
    ctx.arc(punto.x, punto.y, tamano, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${actual.color}, ${brillo})`;
    ctx.shadowBlur = punto.profundidad > 0.7 ? 7 : 0;
    ctx.shadowColor = `rgba(${actual.color}, 0.85)`;
    ctx.fill();
  }

  ctx.shadowBlur = 0;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-angulo * 0.35);
  ctx.strokeStyle = `rgba(${actual.color}, 0.28)`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(0, 0, radio * 1.28, radio * 0.25, -0.48, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([2, 11]);
  ctx.strokeStyle = `rgba(${actual.color}, 0.48)`;
  ctx.beginPath();
  ctx.arc(0, 0, radio * 1.14, 0.18, Math.PI * 1.25);
  ctx.stroke();
  ctx.restore();

  requestAnimationFrame(dibujarNucleo);
}

function cambiarEstado(valor) {
  if (valor === "apagando") {
    apagando = true;
    document.body.dataset.estado = valor;
    estadoVisual.textContent = "APAGÁNDOSE";
    document.getElementById("estado-microfono").textContent = "DETENIÉNDOSE";
    cerrarConfirmacion();
    window.setTimeout(() => {
      window.close();
      if (!window.closed) window.location.replace("about:blank");
    }, 250);
    return;
  }
  if (!Object.hasOwn(ESTADOS, valor)) return;
  estado = valor;
  document.body.dataset.estado = valor;
  estadoVisual.textContent = ESTADOS[valor].etiqueta;
  actividadVoz.textContent = {
    reposo: "ESPERANDO ACTIVACIÓN",
    escuchando: "CAPTURANDO VOZ",
    pensando: "ANALIZANDO SOLICITUD",
    hablando: "RESPONDIENDO EN VOZ",
  }[valor];
  if (valor === "escuchando") {
    document.getElementById("estado-microfono").textContent = "ESCUCHANDO";
  } else if (valor === "hablando" || valor === "pensando" || valor === "reposo") {
    document.getElementById("estado-microfono").textContent = "ACTIVO";
  }
}

function agregar(quien, texto) {
  const mensaje = document.createElement("article");
  mensaje.className = `mensaje ${quien === "Jarvis" ? "jarvis" : "tu"}`;

  const meta = document.createElement("span");
  meta.className = "mensaje-meta";
  meta.textContent = `${quien === "Jarvis" ? "J.A.R.V.I.S." : "TÚ"}  /  ${new Date().toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}`;

  const contenido = document.createElement("p");
  contenido.className = "mensaje-texto";
  contenido.textContent = texto;
  mensaje.append(meta, contenido);
  chat.appendChild(mensaje);
  chat.scrollTop = chat.scrollHeight;
}

function actualizarConexion(conectado) {
  conexionIndicador.classList.toggle("conectado", conectado);
  conexionIndicador.classList.toggle("desconectado", !conectado);
  conexionTexto.textContent = conectado ? "EN LÍNEA" : "SIN CONEXIÓN";
}

function cerrarConfirmacion() {
  accionPendiente = null;
  if (dialogo.open) dialogo.close();
}

function conectar() {
  const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocolo}//${location.host}/ws`);

  socket.onopen = () => actualizarConexion(true);
  socket.onmessage = (evento) => {
    const datos = JSON.parse(evento.data);
    if (datos.tipo === "estado") cambiarEstado(datos.valor);
    if (datos.tipo === "voz_sistema") {
      const etiquetas = {
        iniciando: "INICIANDO",
        activo: "ACTIVO",
        falta_huella: "REGISTRO REQUERIDO",
        error: "ERROR",
      };
      document.getElementById("estado-microfono").textContent =
        etiquetas[datos.valor] || "NO DISPONIBLE";
    }
    if (datos.tipo === "respuesta") agregar("Jarvis", datos.texto);
    if (datos.tipo === "usuario") agregar("Tú", datos.texto);
    if (datos.tipo === "confirmacion_requerida") {
      accionPendiente = datos.id;
      document.getElementById("confirmacion-detalle").textContent =
        `Jarvis solicita permiso para: ${datos.detalle}.`;
      if (!dialogo.open) dialogo.showModal();
    }
    if (datos.tipo === "aviso") agregar("Jarvis", datos.texto);
  };
  socket.onclose = () => {
    actualizarConexion(false);
    cerrarConfirmacion();
    if (!apagando) window.setTimeout(conectar, 1800);
  };
  socket.onerror = () => socket.close();
}

function mandar(tipo, extra = {}) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ tipo, ...extra }));
    return true;
  }
  agregar("Jarvis", "No hay conexión con el servidor. Inténtalo de nuevo en unos segundos.");
  return false;
}

function enviarTexto(evento) {
  evento.preventDefault();
  const texto = caja.value.trim();
  if (!texto) return;
  agregar("Tú", texto);
  caja.value = "";
  mandar("texto", { texto });
}

document.getElementById("formulario-chat").addEventListener("submit", enviarTexto);

document.getElementById("detener-voz").addEventListener("click", () =>
  mandar("detener_voz"),
);

document.getElementById("voz").addEventListener("change", (evento) => {
  document.getElementById("estado-audio").textContent = evento.target.checked ? "ACTIVO" : "SILENCIADO";
  mandar("voz", { valor: evento.target.checked });
});

document.getElementById("proveedor").addEventListener("change", (evento) =>
  mandar("proveedor", { valor: evento.target.value }),
);

document.querySelectorAll("[data-atajo]").forEach((boton) => {
  boton.addEventListener("click", () => mandar("atajo", { valor: boton.dataset.atajo }));
});

document.getElementById("confirmar-accion").addEventListener("click", () => {
  if (accionPendiente) mandar("confirmar_atajo", { id: accionPendiente });
  cerrarConfirmacion();
});

document.getElementById("cancelar-accion").addEventListener("click", () => {
  if (accionPendiente) mandar("cancelar_atajo", { id: accionPendiente });
  cerrarConfirmacion();
});

function actualizarReloj() {
  document.getElementById("reloj").textContent = new Date().toLocaleTimeString("es", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

window.setInterval(actualizarReloj, 1000);
actualizarReloj();
conectar();
dibujarNucleo();
agregar("Jarvis", "Sistemas en línea. Tu asistente está listo para recibir instrucciones.");
