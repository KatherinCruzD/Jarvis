const canvas = document.getElementById("nucleo");
const ctx = canvas.getContext("2d");
let ancho = 0;
let alto = 0;

function ajustar() {
  ancho = canvas.width = window.innerWidth;
  alto = canvas.height = window.innerHeight;
}
window.addEventListener("resize", ajustar);
ajustar();

// Puntos repartidos sobre una esfera
const TOTAL = 600;
const puntos = [];
for (let i = 0; i < TOTAL; i++) {
  const y = 1 - (i / (TOTAL - 1)) * 2;
  const radio = Math.sqrt(1 - y * y);
  const theta = i * Math.PI * (3 - Math.sqrt(5));
  puntos.push({ x: Math.cos(theta) * radio, y: y, z: Math.sin(theta) * radio });
}

const ESTADOS = {
  reposo: { velocidad: 0.003, amplitud: 0.02, color: "0,200,255" },
  escuchando: { velocidad: 0.008, amplitud: 0.08, color: "80,255,180" },
  pensando: { velocidad: 0.02, amplitud: 0.05, color: "255,200,60" },
  hablando: { velocidad: 0.006, amplitud: 0.12, color: "0,220,255" },
};

let estado = "reposo";
let angulo = 0;
let pulso = 0;

function dibujar() {
  const e = ESTADOS[estado] || ESTADOS.reposo;
  ctx.clearRect(0, 0, ancho, alto);

  angulo += e.velocidad;
  pulso += 0.08;
  const base = Math.min(ancho, alto) * 0.22;
  const radio = base * (1 + Math.sin(pulso) * e.amplitud);
  const cx = ancho / 2;
  const cy = alto / 2;
  const cos = Math.cos(angulo);
  const sen = Math.sin(angulo);

  for (const p of puntos) {
    const x = p.x * cos - p.z * sen;
    const z = p.x * sen + p.z * cos;
    const profundidad = (z + 1) / 2;
    ctx.beginPath();
    ctx.arc(cx + x * radio, cy + p.y * radio, 0.8 + profundidad * 1.8, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${e.color}, ${0.15 + profundidad * 0.85})`;
    ctx.fill();
  }

  ctx.beginPath();
  ctx.arc(cx, cy, radio * 1.25, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(${e.color}, 0.25)`;
  ctx.lineWidth = 1;
  ctx.stroke();

  requestAnimationFrame(dibujar);
}
dibujar();

// Comunicación con Python
const chat = document.getElementById("chat");
const caja = document.getElementById("caja");
let socket;

function conectar() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage = (evento) => {
    const datos = JSON.parse(evento.data);
    if (datos.tipo === "estado") estado = datos.valor;
    if (datos.tipo === "respuesta") agregar("Jarvis", datos.texto);
  };
  socket.onclose = () => setTimeout(conectar, 2000);
}
conectar();

function mandar(tipo, extra = {}) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ tipo, ...extra }));
  }
}

function agregar(quien, texto) {
  const linea = document.createElement("p");
  linea.className = quien === "Jarvis" ? "jarvis" : "tu";
  linea.textContent = `${quien}: ${texto}`;
  chat.appendChild(linea);
  chat.scrollTop = chat.scrollHeight;
}

function enviarTexto() {
  const texto = caja.value.trim();
  if (!texto) return;
  agregar("Tú", texto);
  caja.value = "";
  mandar("texto", { texto });
}

document.getElementById("enviar").onclick = enviarTexto;
caja.addEventListener("keydown", (e) => {
  if (e.key === "Enter") enviarTexto();
});
document.getElementById("voz").onchange = (e) =>
  mandar("voz", { valor: e.target.checked });
document.getElementById("proveedor").onchange = (e) =>
  mandar("proveedor", { valor: e.target.value });
document.querySelectorAll("[data-atajo]").forEach((boton) => {
  boton.onclick = () => mandar("atajo", { valor: boton.dataset.atajo });
});

agregar("Jarvis", "Sistemas en línea. ¿En qué te ayudo?");