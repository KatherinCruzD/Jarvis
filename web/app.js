const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const store = {
  read(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch (error) {
      console.error(`No se pudo leer ${key} del almacenamiento local.`, error);
      return fallback;
    }
  },
  write(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error(`No se pudo guardar ${key} en el almacenamiento local.`, error);
      dice("No pude guardar los cambios en este navegador.");
    }
  },
};

let ws;
let estado = "reposo";
let conectado = false;
let tFin;
let climaPendiente = false;
const estados = ["reposo", "escuchando", "pensando", "hablando", "procesando", "sinvoz"];
const nombresEstado = { escuchando: "Escuchando", pensando: "Pensando", hablando: "Hablando", procesando: "Procesando", sinvoz: "No te oí" };
const colores = { reposo: [25, 200, 255], escuchando: [70, 255, 176], pensando: [255, 197, 61], hablando: [25, 200, 255], procesando: [169, 139, 255], sinvoz: [255, 107, 134] };

$("#est").innerHTML = Object.entries(nombresEstado).map(([key, name]) => `<span data-e="${key}">${name}</span>`).join("");

function setEstado(value) {
  const previous = estado;
  estado = estados.includes(value) ? value : "reposo";
  document.body.dataset.e = estado;
  $$("#est span").forEach((item) => item.classList.toggle("a", item.dataset.e === estado));
  const estadoMic = ({
    reposo: "Micrófono activo · di «Jarvis»",
    escuchando: "Reconociendo tu voz…",
    pensando: "Procesando tu solicitud…",
    hablando: "Micrófono activo mientras Jarvis responde",
    procesando: "Ejecutando tu solicitud…",
    sinvoz: "No se reconoció la voz",
  })[estado];
  $("#mic-status").textContent = conectado ? estadoMic : "Servidor desconectado · voz no disponible";
  if (previous === "hablando" && estado === "reposo") {
    document.body.classList.add("fin");
    clearTimeout(tFin);
    tFin = setTimeout(() => document.body.classList.remove("fin"), 1800);
  }
}

function send(message) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
    return true;
  }
  $("#on").textContent = "Sin conexión";
  return false;
}

function log(who, text) {
  const entry = document.createElement("p");
  entry.className = who === "Jarvis" ? "j" : "u";
  entry.textContent = `${who}: ${text}`;
  $("#log").append(entry);
  $("#log").scrollTop = $("#log").scrollHeight;
}

function dice(text) {
  $("#bur").textContent = text.length > 170 ? `${text.slice(0, 167)}…` : text;
  log("Jarvis", text);
  const face = $("#cara");
  face.classList.remove("re");
  void face.offsetWidth;
  face.classList.add("re");
}

function pedir(text) {
  const command = text.trim();
  if (!command) return false;
  log("Tú", command);
  setEstado("procesando");
  if (!send({ tipo: "texto", texto: command })) {
    setEstado("sinvoz");
    dice("No hay conexión con Jarvis. Comprueba que el servidor siga abierto.");
    return false;
  }
  return true;
}

function conectar() {
  if (location.protocol === "file:") {
    $("#on").textContent = "Abre Jarvis desde el servidor";
    return;
  }
  try {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`);
  } catch (error) {
    console.error("No se pudo crear la conexión con Jarvis.", error);
    $("#on").textContent = "Error de conexión";
    setTimeout(conectar, 3000);
    return;
  }
  ws.onopen = () => {
    conectado = true;
    $("#on").textContent = "Conectado";
    $("#mic-status").textContent = "Micrófono conectado · di «Jarvis»";
    $("#d3").textContent = navigator.onLine ? "Conectado" : "Sin conexión";
    send({ tipo: "voz", valor: $("#voz").checked });
    send({ tipo: "proveedor", valor: $("#prov").value });
  };
  ws.onclose = () => {
    conectado = false;
    $("#on").textContent = "Reconectando…";
    $("#mic-status").textContent = "Servidor desconectado · voz no disponible";
    $("#d3").textContent = "Servidor desconectado";
    setTimeout(conectar, 2500);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (error) {
      console.error("Jarvis envió un mensaje que no es JSON válido.", error);
      return;
    }
    if (data.tipo === "estado") setEstado(data.valor);
    else if (data.tipo === "respuesta") {
      if (climaPendiente) {
        $("#clima").textContent = data.texto;
        const ciudad = data.texto.match(/^En ([^,]+) hay/i);
        if (ciudad) $("#d4").textContent = ciudad[1];
        climaPendiente = false;
      }
      dice(data.texto);
      setEstado("reposo");
    }
    else if (data.tipo === "usuario") log("Tú", data.texto);
    else if (data.tipo === "voz_sistema") {
      const status = {
        iniciando: "Micrófono iniciando…",
        activo: "Micrófono activo · di «Jarvis»",
        falta_huella: "Registra tu voz para activar Jarvis",
        error: "Error al iniciar el micrófono",
      };
      $("#mic-status").textContent = status[data.valor] || "Micrófono no disponible";
    }
    else if (data.tipo === "modo" && data.valor === "privado") $("#mic-status").textContent = "Micrófono pausado · modo privado";
    else if (data.tipo === "confirmacion_requerida") {
      if (window.confirm(`Jarvis solicita permiso para:\n\n${data.detalle}\n\n¿Autorizar esta acción?`)) send({ tipo: "confirmar_atajo", id: data.id });
      else send({ tipo: "cancelar_atajo", id: data.id });
    } else if (data.tipo === "aviso") dice(data.texto);
    else if (data.tipo === "sistema") actualizarSistema(data);
    else if (data.tipo === "musica") $("#mus").textContent = [data.titulo, data.artista].filter(Boolean).join(" – ") || "Sin reproducción detectada";
    else window.dispatchEvent(new CustomEvent("jarvis", { detail: data }));
  };
}

function anillo(selector, value, label) {
  const ring = $(selector);
  ring.style.setProperty("--v", Number(value) || 0);
  ring.querySelector("b").textContent = label ?? `${Math.round(value)}%`;
}

const historialCpu = [];
function actualizarSistema(data) {
  anillo("#rc", data.cpu);
  anillo("#rr", data.ram);
  anillo("#rd", data.disco);
  anillo("#rb", data.bateria, data.bateria == null ? "–" : `${Math.round(data.bateria)}%`);
  $("#tmp").textContent = data.temp == null ? "–" : `${Math.round(data.temp)}°C`;
  $("#red").textContent = data.red == null ? "–" : `${Number(data.red).toFixed(1)} MB/s`;
  historialCpu.push(Number(data.cpu) || 0);
  if (historialCpu.length > 40) historialCpu.shift();
  dibujarGrafica();
}

function dibujarGrafica() {
  const canvas = $("#spk");
  const ctx = canvas.getContext("2d");
  const width = canvas.width = canvas.clientWidth;
  const height = canvas.height = canvas.clientHeight;
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--c");
  ctx.lineWidth = 2;
  ctx.beginPath();
  historialCpu.forEach((value, index) => {
    const x = index * width / Math.max(1, historialCpu.length - 1);
    const y = height - 4 - value / 100 * (height - 8);
    if (index) ctx.lineTo(x, y); else ctx.moveTo(x, y);
  });
  ctx.stroke();
}

async function actualizarTelemetria() {
  if (!conectado) return;
  try {
    const response = await fetch("/api/telemetria", { cache: "no-store" });
    if (!response.ok) throw new Error(`El servidor respondió ${response.status}.`);
    const data = await response.json();
    actualizarSistema({ cpu: data.cpu, ram: data.ram, disco: data.disco, bateria: data.bateria, temp: data.temperatura, red: data.red });
  } catch (error) {
    console.error("No se pudo actualizar la telemetría del computador.", error);
    $("#tmp").textContent = "No disponible";
    $("#red").textContent = "No disponible";
  }
}

function reloj() {
  const now = new Date();
  $("#hora").textContent = now.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
  $("#d1").textContent = now.toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
  $("#d2").textContent = now.toLocaleTimeString("es-CO");
  $("#d3").textContent = navigator.onLine ? (conectado ? "Conectado" : "Conectando…") : "Sin conexión";
}
setInterval(reloj, 1000);
reloj();

const aplicaciones = [
  ["chrome", "Chrome", "🌐", "https://www.google.com/chrome/"], ["youtube", "YouTube", "▶️", "https://www.youtube.com/"],
  ["discord", "Discord", "🎮", "https://discord.com/app"], ["vscode", "VS Code", "🧩"], ["spotify", "Spotify", "🟢"],
  ["steam", "Steam", "🎮", "https://store.steampowered.com/"], ["whatsapp", "WhatsApp", "🟩", "https://web.whatsapp.com/"],
  ["minecraft", "Minecraft", "🟫", "https://www.minecraft.net/"], ["word", "Word", "📝"], ["gmail", "Gmail", "✉️", "https://mail.google.com/"],
  ["tiktok", "TikTok", "🎵", "https://www.tiktok.com/"], ["drive", "Drive", "☁️", "https://drive.google.com/"],
];
for (const [key, name, emoji, url] of aplicaciones) {
  const button = document.createElement("button");
  button.className = "ap";
  const icon = document.createElement("em");
  icon.textContent = emoji;
  const label = document.createElement("span");
  label.textContent = name;
  button.append(icon, label);
  button.addEventListener("click", () => {
    if (url) window.open(url, "_blank", "noopener,noreferrer");
    else if (send({ tipo: "atajo", valor: key })) log("Tú", `Abriendo ${name}.`);
    else dice("No hay conexión con Jarvis para abrir esta aplicación.");
  });
  $("#apps").append(button);
}

$("#env").addEventListener("click", () => {
  const field = $("#caja");
  const text = field.value.trim();
  if (text) { field.value = ""; pedir(text); }
});
$("#caja").addEventListener("keydown", (event) => { if (event.key === "Enter") $("#env").click(); });
const parar = () => { send({ tipo: "detener_voz" }); setEstado("reposo"); };
$("#det").addEventListener("click", parar);
window.addEventListener("keydown", (event) => { if (event.key === "F8") { event.preventDefault(); parar(); } });
$("#voz").addEventListener("change", (event) => send({ tipo: "voz", valor: event.target.checked }));
$("#prov").addEventListener("change", (event) => send({ tipo: "proveedor", valor: event.target.value }));
$$("[data-t]").forEach((button) => button.addEventListener("click", () => pedir(button.dataset.t)));
$("#abrir").addEventListener("click", () => {
  const name = window.prompt("¿Qué programa quieres abrir?");
  if (name?.trim()) pedir(`abre ${name.trim()}`);
});

function abrirBusqueda(base, query) {
  if (!query) return;
  window.open(`${base}${encodeURIComponent(query)}`, "_blank", "noopener,noreferrer");
}
$("#bg").addEventListener("click", () => abrirBusqueda("https://www.google.com/search?q=", $("#bq").value.trim()));
$("#by").addEventListener("click", () => abrirBusqueda("https://www.youtube.com/results?search_query=", $("#bq").value.trim()));
$("#bw").addEventListener("click", () => abrirBusqueda("https://es.wikipedia.org/w/index.php?search=", $("#bq").value.trim()));
$("#bq").addEventListener("keydown", (event) => { if (event.key === "Enter") $("#bg").click(); });
$("#tb").addEventListener("click", () => {
  const text = $("#tq").value.trim();
  if (!text) return;
  pedir(`traduce de ${$("#tf").selectedOptions[0].textContent} al ${$("#ti").selectedOptions[0].textContent}: ${text}`);
});
$("#tq").addEventListener("keydown", (event) => { if (event.key === "Enter") $("#tb").click(); });
$("#ab").addEventListener("click", () => {
  const name = $("#aq").value.trim();
  if (name) { $("#arch").textContent = "Buscando en el equipo…"; pedir(`busca en el explorador de archivos un archivo llamado ${name}`); }
});
$("#ao").addEventListener("click", () => {
  const name = $("#aq").value.trim();
  if (name) { $("#arch").textContent = "Solicitando abrir el archivo…"; pedir(`abre el archivo llamado ${name}`); }
});
$("#aq").addEventListener("keydown", (event) => { if (event.key === "Enter") $("#ab").click(); });
$("#pw").addEventListener("click", () => { if (window.confirm("¿Quieres cerrar Jarvis?")) pedir("Jarvis, duérmete"); });

let fontSize = store.read("jv_fs", 1.05);
let ligero = store.read("jv_lig", false);
function aplicarFuente() { document.documentElement.style.setProperty("--fs", `${fontSize}vw`); store.write("jv_fs", fontSize); }
aplicarFuente();
$("#fm").addEventListener("click", () => { fontSize = Math.max(.8, fontSize - .1); aplicarFuente(); });
$("#fp").addEventListener("click", () => { fontSize = Math.min(1.6, fontSize + .1); aplicarFuente(); });
$("#lg").addEventListener("click", () => {
  ligero = !ligero;
  store.write("jv_lig", ligero);
  document.body.classList.toggle("ligero", ligero);
  $("#lg").style.borderColor = ligero ? "var(--c)" : "";
});
document.body.classList.toggle("ligero", ligero);
$("#lg").style.borderColor = ligero ? "var(--c)" : "";
$("#notas").value = store.read("jv_notas", "");
$("#notas").addEventListener("input", (event) => store.write("jv_notas", event.target.value));

function dibujarLista(element, items, storageKey, redraw) {
  element.replaceChildren();
  items.forEach((item, index) => {
    const row = document.createElement("li");
    row.className = item.h ? "h" : "";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = Boolean(item.h);
    check.addEventListener("change", () => { item.h = check.checked; store.write(storageKey, items); redraw(); });
    const label = document.createElement("span");
    label.textContent = item.x;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕";
    remove.setAttribute("aria-label", "Borrar");
    remove.addEventListener("click", () => { items.splice(index, 1); store.write(storageKey, items); redraw(); });
    row.append(check, label, remove);
    element.append(row);
  });
}

let tareas = store.read("jv_tareas", []);
if (!Array.isArray(tareas)) tareas = [];
const dibujarTareas = () => dibujarLista($("#tar"), tareas, "jv_tareas", dibujarTareas);
dibujarTareas();
$("#ta").addEventListener("click", () => {
  const text = $("#tn").value.trim();
  if (text) { tareas.push({ x: text, h: false }); $("#tn").value = ""; store.write("jv_tareas", tareas); dibujarTareas(); }
});
$("#tn").addEventListener("keydown", (event) => { if (event.key === "Enter") $("#ta").click(); });

function calendarKey(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`; }
let eventos = store.read("jv_ev", {});
if (!eventos || typeof eventos !== "object" || Array.isArray(eventos)) eventos = {};
const today = new Date();
let month = new Date(today.getFullYear(), today.getMonth(), 1);
let selected = calendarKey(today);
function dibujarCalendario() {
  $("#ct").textContent = month.toLocaleDateString("es-CO", { month: "long", year: "numeric" });
  const calendar = $("#cal");
  calendar.replaceChildren(...["L", "M", "M", "J", "V", "S", "D"].map((day) => { const label = document.createElement("b"); label.textContent = day; return label; }));
  const offset = (month.getDay() + 6) % 7;
  const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  for (let index = 0; index < offset; index += 1) calendar.append(document.createElement("span"));
  for (let day = 1; day <= count; day += 1) {
    const date = new Date(month.getFullYear(), month.getMonth(), day);
    const key = calendarKey(date);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = String(day);
    if (key === calendarKey(today)) button.classList.add("hoy");
    if (key === selected) button.classList.add("sel");
    if ((eventos[key] || []).length) button.classList.add("ev");
    button.addEventListener("click", () => { selected = key; dibujarCalendario(); });
    calendar.append(button);
  }
  dibujarLista($("#ev"), eventos[selected] || [], "jv_ev", dibujarCalendario);
}
$("#cm").addEventListener("click", () => { month = new Date(month.getFullYear(), month.getMonth() - 1, 1); dibujarCalendario(); });
$("#cs").addEventListener("click", () => { month = new Date(month.getFullYear(), month.getMonth() + 1, 1); dibujarCalendario(); });
$("#ea").addEventListener("click", () => {
  const text = $("#en").value.trim();
  if (text) { (eventos[selected] ||= []).push({ x: text, h: false }); $("#en").value = ""; store.write("jv_ev", eventos); dibujarCalendario(); }
});
$("#en").addEventListener("keydown", (event) => { if (event.key === "Enter") $("#ea").click(); });
dibujarCalendario();

$("#actualizar-clima").addEventListener("click", () => {
  $("#clima").textContent = "Consultando el clima configurado para Jarvis…";
  climaPendiente = pedir("cómo está el clima");
});

window.addEventListener("online", () => { $("#d3").textContent = "Conectado"; });
window.addEventListener("offline", () => { $("#d3").textContent = "Sin conexión"; });

const orb = $("#orb");
const orbContext = orb.getContext("2d");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const points = [];
for (let index = 0; index < 360; index += 1) {
  const y = 1 - 2 * index / 359;
  const radius = Math.sqrt(1 - y * y);
  const angle = index * 2.39996;
  points.push([Math.cos(angle) * radius, y, Math.sin(angle) * radius]);
}
let width = 0;
let height = 0;
let angle = 0;
let pulse = 0;
let color = [...colores.reposo];
function ajustarOrb() { const rect = orb.getBoundingClientRect(); width = orb.width = rect.width; height = orb.height = rect.height; }
window.addEventListener("resize", ajustarOrb);
ajustarOrb();
function dibujarOrb() {
  const target = colores[estado] || colores.reposo;
  color = color.map((value, index) => value + (target[index] - value) * .08);
  const rgb = color.map(Math.round).join(",");
  const radius = Math.min(width, height * 1.1) * .2 * (1 + Math.sin(pulse) * .03);
  const centerX = width / 2;
  const centerY = height * .62;
  orbContext.clearRect(0, 0, width, height);
  const motionScale = ligero || reducedMotion ? .3 : 1;
  angle += ({ reposo: .003, escuchando: .007, pensando: .02, hablando: .006, procesando: .014, sinvoz: .002 })[estado] * motionScale;
  pulse += estado === "hablando" ? .25 : .05;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const glow = orbContext.createRadialGradient(centerX, centerY, radius * .2, centerX, centerY, radius * 1.3);
  glow.addColorStop(0, `rgba(${rgb},.28)`);
  glow.addColorStop(1, `rgba(${rgb},0)`);
  orbContext.fillStyle = glow;
  orbContext.beginPath();
  orbContext.arc(centerX, centerY, radius * 1.3, 0, Math.PI * 2);
  orbContext.fill();
  for (let index = 0; index < points.length; index += ligero || reducedMotion ? 2 : 1) {
    const point = points[index];
    const x = point[0] * cos - point[2] * sin;
    const z = point[0] * sin + point[2] * cos;
    const depth = (z + 1) / 2;
    orbContext.fillStyle = `rgba(${rgb},${.12 + depth * .88})`;
    orbContext.beginPath();
    orbContext.arc(centerX + x * radius, centerY + point[1] * radius, .7 + depth * 1.9, 0, Math.PI * 2);
    orbContext.fill();
  }
  requestAnimationFrame(dibujarOrb);
}
setEstado("reposo");
requestAnimationFrame(dibujarOrb);
setInterval(actualizarTelemetria, 5000);
conectar();
