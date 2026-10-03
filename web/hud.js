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
let modoActual = "escucha";
let angulo = 0;
let pulso = 0;
let apagando = false;
let fechaCalendario = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let fechaSeleccionada = new Date();
const notificaciones = [];

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
  const estadoBase = ESTADOS[estado] || ESTADOS.reposo;
  const actual = modoActual === "privado"
    ? { ...estadoBase, color: "255, 91, 111", velocidad: 0.0012 }
    : estado === "reposo" && modoActual === "escucha"
      ? { ...estadoBase, color: "113, 255, 197" }
      : estadoBase;
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

function cambiarModo(valor) {
  if (!["escucha", "conversacion", "privado"].includes(valor)) return;
  modoActual = valor;
  document.body.dataset.modo = valor;
  document.querySelectorAll(".modo[data-modo]").forEach((boton) => {
    const activo = boton.dataset.modo === valor;
    boton.classList.toggle("activo", activo);
    boton.setAttribute("aria-pressed", String(activo));
  });
  if (valor === "privado") {
    actividadVoz.textContent = "MODO PRIVADO · MICRÓFONO CERRADO";
    document.getElementById("estado-microfono").textContent = "PRIVADO";
    estadoVisual.textContent = "MODO PRIVADO";
  } else if (valor === "conversacion") {
    actividadVoz.textContent = "CONVERSACIÓN · CONTEXTO 20 S";
    document.getElementById("estado-microfono").textContent = "ESCUCHANDO";
    estadoVisual.textContent = "MODO CONVERSACIÓN";
  } else {
    actividadVoz.textContent = "ESPERANDO ACTIVACIÓN";
    document.getElementById("estado-microfono").textContent = "ACTIVO";
    estadoVisual.textContent = "MODO ESCUCHA";
  }
}

function guardarLocal(clave, valor, estadoElemento) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor));
    if (estadoElemento) estadoElemento.textContent = "Guardado en este navegador.";
    return true;
  } catch (error) {
    console.error(`No se pudo guardar ${clave} localmente.`, error);
    if (estadoElemento) estadoElemento.textContent = "No se pudo guardar en este navegador.";
    return false;
  }
}

function leerLocal(clave, valorInicial) {
  try {
    const valor = localStorage.getItem(clave);
    return valor === null ? valorInicial : JSON.parse(valor);
  } catch (error) {
    console.error(`No se pudo leer ${clave} localmente.`, error);
    return valorInicial;
  }
}

function agregarNotificacion(texto) {
  notificaciones.unshift(texto);
  notificaciones.length = Math.min(notificaciones.length, 4);
  const lista = document.getElementById("lista-notificaciones");
  lista.replaceChildren(...notificaciones.map((notificacion) => {
    const item = document.createElement("li");
    item.textContent = notificacion;
    return item;
  }));
  document.getElementById("contador-notificaciones").textContent =
    String(notificaciones.length).padStart(2, "0");
}

let tareas = leerLocal("jarvis-tareas-hud", []);
if (!Array.isArray(tareas)) tareas = [];

function dibujarTareas() {
  const lista = document.getElementById("lista-tareas");
  lista.replaceChildren();
  if (!tareas.length) {
    const vacia = document.createElement("li");
    vacia.className = "vacia";
    vacia.textContent = "No tienes tareas todavía.";
    lista.append(vacia);
    return;
  }

  tareas.forEach((tarea, indice) => {
    const item = document.createElement("li");
    item.className = `tarea${tarea.completada ? " completada" : ""}`;
    const casilla = document.createElement("input");
    casilla.type = "checkbox";
    casilla.checked = Boolean(tarea.completada);
    casilla.setAttribute("aria-label", `Completar ${tarea.texto}`);
    casilla.addEventListener("change", () => {
      tareas[indice].completada = casilla.checked;
      guardarLocal("jarvis-tareas-hud", tareas);
      dibujarTareas();
    });
    const texto = document.createElement("span");
    texto.textContent = tarea.texto;
    const eliminar = document.createElement("button");
    eliminar.className = "tarea-eliminar";
    eliminar.type = "button";
    eliminar.textContent = "×";
    eliminar.setAttribute("aria-label", `Eliminar ${tarea.texto}`);
    eliminar.addEventListener("click", () => {
      tareas.splice(indice, 1);
      guardarLocal("jarvis-tareas-hud", tareas);
      dibujarTareas();
    });
    item.append(casilla, texto, eliminar);
    lista.append(item);
  });
}

function dibujarCalendario() {
  const contenedor = document.getElementById("calendario");
  const titulo = document.getElementById("titulo-calendario");
  titulo.textContent = fechaCalendario.toLocaleDateString("es", {
    month: "long",
    year: "numeric",
  }).toUpperCase();
  contenedor.replaceChildren();
  ["L", "M", "X", "J", "V", "S", "D"].forEach((dia) => {
    const encabezado = document.createElement("span");
    encabezado.textContent = dia;
    contenedor.append(encabezado);
  });
  const primerDia = (fechaCalendario.getDay() + 6) % 7;
  const diasEnMes = new Date(
    fechaCalendario.getFullYear(),
    fechaCalendario.getMonth() + 1,
    0,
  ).getDate();
  for (let vacio = 0; vacio < primerDia; vacio += 1) {
    contenedor.append(document.createElement("span"));
  }
  for (let dia = 1; dia <= diasEnMes; dia += 1) {
    const boton = document.createElement("button");
    const fecha = new Date(
      fechaCalendario.getFullYear(),
      fechaCalendario.getMonth(),
      dia,
    );
    boton.type = "button";
    boton.textContent = String(dia);
    if (fecha.toDateString() === new Date().toDateString()) boton.classList.add("hoy");
    if (fecha.toDateString() === fechaSeleccionada.toDateString()) {
      boton.classList.add("seleccionado");
    }
    boton.setAttribute("aria-label", fecha.toLocaleDateString("es"));
    boton.addEventListener("click", () => {
      fechaSeleccionada = fecha;
      dibujarCalendario();
    });
    contenedor.append(boton);
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
  if (quien === "Jarvis") agregarNotificacion(texto);
}

function actualizarConexion(conectado) {
  conexionIndicador.classList.toggle("conectado", conectado);
  conexionIndicador.classList.toggle("desconectado", !conectado);
  conexionTexto.textContent = conectado ? "EN LÍNEA" : "SIN CONEXIÓN";
  const estadoServidor = document.querySelector(".telemetria-titulo");
  estadoServidor.classList.toggle("desconectado", !conectado);
  document.getElementById("telemetria-servidor").textContent =
    conectado ? "JARVIS ONLINE" : "JARVIS OFFLINE";
}

function actualizarRed() {
  const conectado = navigator.onLine;
  const indicador = document.getElementById("telemetria-red");
  indicador.textContent = conectado ? "CONECTADO" : "SIN RED";
  indicador.classList.toggle("conectado", conectado);
  indicador.classList.toggle("desconectado", !conectado);
}

async function actualizarTelemetria() {
  try {
    const respuesta = await fetch("/api/telemetria", { cache: "no-store" });
    if (!respuesta.ok) {
      throw new Error(`El servidor respondió ${respuesta.status}.`);
    }
    const datos = await respuesta.json();
    document.getElementById("telemetria-cpu").textContent = `${datos.cpu}%`;
    document.getElementById("telemetria-ram").textContent = `${datos.ram}%`;
    document.getElementById("cpu-panel").textContent = `${datos.cpu}%`;
    document.getElementById("ram-panel").textContent = `${datos.ram}%`;
    document.getElementById("medidor-cpu").style.setProperty(
      "--nivel",
      `${datos.cpu}%`,
    );
    document.getElementById("medidor-ram").style.setProperty(
      "--nivel",
      `${datos.ram}%`,
    );
    document.getElementById("telemetria-bateria").textContent =
      datos.bateria === null ? "N/D" : `${datos.bateria}%`;
    document.getElementById("bateria-panel").textContent =
      datos.bateria === null ? "N/D" : `${datos.bateria}%`;
    if (datos.bateria !== null) {
      document.getElementById("medidor-bateria").style.setProperty(
        "--nivel",
        `${datos.bateria}%`,
      );
    }
    document.getElementById("telemetria-temperatura").textContent =
      datos.temperatura === null ? "N/D" : `${datos.temperatura}°C`;
  } catch (error) {
    document.getElementById("telemetria-cpu").textContent = "--";
    document.getElementById("telemetria-ram").textContent = "--";
    document.getElementById("cpu-panel").textContent = "--%";
    document.getElementById("ram-panel").textContent = "--%";
    document.getElementById("telemetria-bateria").textContent = "--";
    document.getElementById("bateria-panel").textContent = "--";
    document.getElementById("telemetria-temperatura").textContent = "--";
    console.error("No se pudo actualizar la telemetría del computador.", error);
  }
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
    if (datos.tipo === "modo") cambiarModo(datos.valor);
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

document.querySelectorAll(".modo[data-modo]").forEach((boton) => {
  boton.addEventListener("click", () => mandar("modo", { valor: boton.dataset.modo }));
});

document.querySelectorAll("[data-atajo]").forEach((boton) => {
  boton.addEventListener("click", () => mandar("atajo", { valor: boton.dataset.atajo }));
});

function enviarComandoHud(texto) {
  const comando = texto.trim();
  if (!comando) return;
  agregar("Tú", comando);
  mandar("texto", { texto: comando });
}

document.getElementById("formulario-buscador").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const consulta = document.getElementById("buscador-integrado").value.trim();
  if (!consulta) return;
  const tipo = document.getElementById("tipo-busqueda").value;
  enviarComandoHud(
    tipo === "archivos"
      ? `busca en el explorador de archivos un archivo llamado: ${consulta}`
      : `busca ${consulta} en Google`,
  );
  document.getElementById("buscador-integrado").value = "";
});

document.getElementById("formulario-archivos").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const nombre = document.getElementById("buscador-archivos").value.trim();
  if (!nombre) return;
  enviarComandoHud(
    evento.submitter?.value === "abrir"
      ? `abre el archivo llamado: ${nombre}`
      : `busca en el explorador de archivos un archivo llamado: ${nombre}`,
  );
});

document.querySelectorAll("[data-musica]").forEach((boton) => {
  boton.addEventListener("click", () => {
    const ordenes = {
      pausa: "pausa la música",
      siguiente: "canción siguiente",
      anterior: "canción anterior",
    };
    enviarComandoHud(ordenes[boton.dataset.musica]);
  });
});

const blocNotas = document.getElementById("bloc-notas");
const estadoNotas = document.getElementById("estado-notas");
blocNotas.value = leerLocal("jarvis-bloc-notas", "");
blocNotas.addEventListener("input", () => {
  guardarLocal("jarvis-bloc-notas", blocNotas.value, estadoNotas);
});

document.getElementById("formulario-tarea").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const entrada = document.getElementById("nueva-tarea");
  const texto = entrada.value.trim();
  if (!texto) return;
  tareas.push({ texto, completada: false });
  guardarLocal("jarvis-tareas-hud", tareas);
  entrada.value = "";
  dibujarTareas();
});

document.getElementById("limpiar-tareas").addEventListener("click", () => {
  tareas = tareas.filter((tarea) => !tarea.completada);
  guardarLocal("jarvis-tareas-hud", tareas);
  dibujarTareas();
});

document.getElementById("mes-anterior").addEventListener("click", () => {
  fechaCalendario = new Date(
    fechaCalendario.getFullYear(),
    fechaCalendario.getMonth() - 1,
    1,
  );
  dibujarCalendario();
});

document.getElementById("mes-siguiente").addEventListener("click", () => {
  fechaCalendario = new Date(
    fechaCalendario.getFullYear(),
    fechaCalendario.getMonth() + 1,
    1,
  );
  dibujarCalendario();
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
window.setInterval(() => {
  document.getElementById("fecha").textContent = new Date().toLocaleDateString("es", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}, 60000);
document.getElementById("fecha").textContent = new Date().toLocaleDateString("es", {
  weekday: "short",
  day: "2-digit",
  month: "short",
  year: "numeric",
});
dibujarTareas();
dibujarCalendario();
window.addEventListener("online", actualizarRed);
window.addEventListener("offline", actualizarRed);
actualizarRed();
actualizarTelemetria();
window.setInterval(actualizarTelemetria, 5000);
conectar();
dibujarNucleo();
agregar("Jarvis", "Sistemas en línea. Tu asistente está listo para recibir instrucciones.");
