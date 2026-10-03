"use strict";

/* ---------- Configuración ---------- */

// Opciones de ciudad/operador por tipo de transporte.
// "data" apunta al JSON generado con scripts/build_gtfs.py o scripts/build_renfe.py.
// Sin "data" => de momento el trayecto se registra sin línea/paradas y con km manuales.
const CIUDADES = {
  "Autobús": [
    { nombre: "Autobús de Cádiz", data: "data/urbano-cadiz.json" },   // urbano de Cádiz capital (solo línea 1; km aprox.)
    { nombre: "Consorcio Bahía de Cádiz", data: "data/bahia-cadiz.json" },
    { nombre: "TUSSAM Sevilla" },
    { nombre: "EMT Madrid" },
    { nombre: "Otro", otro: true },
  ],
  "Tranvía": [
    { nombre: "Trambahía", data: "data/trambahia.json" },
    { nombre: "Metropolitano de Granada" },
    { nombre: "Otro", otro: true },
  ],
  "Metro": [
    { nombre: "Metro de Madrid", data: "data/madrid-metro.json" },   // líneas 1, 3, 4, 6, 8 y 10
    { nombre: "TMB Barcelona" },
  ],
  "Tren": [
    { nombre: "Cercanías de Cádiz", data: "data/cercanias-cadiz.json" },
    { nombre: "Cercanías de Madrid" },
    { nombre: "Rodalies de Catalunya" },
    { nombre: "Otro", otro: true },
  ],
  "Otro": [
    { nombre: "Otro", otro: true },
  ],
};

const STORAGE_KEY = "trayectos.v1";
const OTRA = "__otra__";     // opción «Otra línea (km a mano)» de los desplegables de línea

/* ---------- Utilidades ---------- */

const $ = (id) => document.getElementById(id);
const el = {
  fecha: $("fecha"), tipo: $("tipo"), ciudad: $("ciudad"), linea: $("linea"),
  sentido: $("sentido"), origen: $("origen"), destino: $("destino"), espera: $("espera"), trayecto: $("trayecto"),
  otroTexto: $("otroTexto"), kmManual: $("kmManual"),
  wrapOtro: $("wrapOtro"), wrapLinea: $("wrapLinea"), wrapSentido: $("wrapSentido"), wrapOrigen: $("wrapOrigen"),
  wrapDestino: $("wrapDestino"), wrapKmManual: $("wrapKmManual"),
  wrapLineaOtra: $("wrapLineaOtra"), lineaOtra: $("lineaOtra"),
  resultado: $("resultado"), kmTexto: $("kmTexto"), kmNota: $("kmNota"),
  error: $("error"), form: $("form"), historial: $("historial"),
};

const cache = {};          // url -> datos GTFS
let datos = null;          // datos del operador seleccionado
let kmActual = null;       // km calculados del trayecto en pantalla

function hoyLocal() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

function fillSelect(sel, items, placeholder) {
  sel.innerHTML = "";
  sel.append(new Option(placeholder, ""));
  items.forEach(([value, label]) => sel.append(new Option(label, value)));
  sel.disabled = items.length === 0;
}

function mostrarError(msg) {
  el.error.textContent = msg || "";
  el.error.hidden = !msg;
}

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- Carga de datos GTFS ---------- */

async function cargarDatos(url) {
  if (cache[url]) return cache[url];
  const r = await fetch(url);
  if (!r.ok) throw new Error("No se pudieron cargar las líneas (" + r.status + ")");
  return (cache[url] = await r.json());
}

/* ---------- Cascada de desplegables ---------- */

function resetDesde(nivel) {
  // niveles: 1 ciudad, 2 línea, 3 sentido, 4 paradas
  if (nivel <= 1) {
    fillSelect(el.ciudad, [], "Selecciona el tipo primero");
    el.wrapOtro.hidden = true; el.otroTexto.value = "";
    datos = null;
  }
  if (nivel <= 2) fillSelect(el.linea, [], "—");
  if (nivel <= 3) fillSelect(el.sentido, [], "—");
  if (nivel <= 4) { fillSelect(el.origen, [], "—"); fillSelect(el.destino, [], "—"); }
  el.wrapKmManual.hidden = true; el.kmManual.value = "";
  el.wrapLineaOtra.hidden = true; el.lineaOtra.value = "";
  kmActual = null; el.resultado.hidden = true;
  mostrarError("");
}

el.tipo.addEventListener("change", () => {
  resetDesde(1);
  const opciones = CIUDADES[el.tipo.value] || [];
  fillSelect(el.ciudad, opciones.map((c) => [c.nombre, c.nombre]), "Selecciona…");
});

el.ciudad.addEventListener("change", async () => {
  resetDesde(2);
  const cfg = (CIUDADES[el.tipo.value] || []).find((c) => c.nombre === el.ciudad.value);
  if (!cfg) return;

  el.wrapOtro.hidden = !cfg.otro;

  if (!cfg.data) {
    // Sin datos aún: registro manual (solo km a mano).
    el.wrapKmManual.hidden = false;
    el.wrapLinea.hidden = el.wrapSentido.hidden = el.wrapOrigen.hidden = el.wrapDestino.hidden = true;
    return;
  }
  el.wrapLinea.hidden = el.wrapSentido.hidden = el.wrapOrigen.hidden = el.wrapDestino.hidden = false;

  try {
    datos = await cargarDatos(cfg.data);
  } catch (e) {
    mostrarError(e.message + ". Puedes guardar el trayecto con km manuales.");
    el.wrapKmManual.hidden = false;
    return;
  }

  const lineas = Object.entries(datos.routes)
    .map(([id, r]) => [id, r.code + " · " + r.name])
    .sort((a, b) => a[1].localeCompare(b[1], "es", { numeric: true }));
  fillSelect(el.linea, lineas, "Selecciona la línea…");
  el.linea.append(new Option("Otra línea (km a mano)", OTRA));
});

el.linea.addEventListener("change", () => {
  resetDesde(3);
  const manual = el.linea.value === OTRA;          // línea sin datos: solo km a mano
  el.wrapSentido.hidden = el.wrapOrigen.hidden = el.wrapDestino.hidden = manual;
  el.wrapKmManual.hidden = el.wrapLineaOtra.hidden = !manual;
  if (!datos || !el.linea.value || manual) return;
  const ruta = datos.routes[el.linea.value];

  // Un sentido por cada dirección del GTFS, etiquetado "Origen → Destino" salvo que el propio
  // operador traiga un headsign fijado a mano (p. ej. cuando la cabecera real de línea no
  // coincide con el nombre de la primera/última parada).
  const sentidos = Object.keys(ruta.dirs).sort().map((dir) => {
    const d = ruta.dirs[dir];
    if (d.headsign) return [dir, d.headsign];
    const ini = datos.stops[d.stops[0][0]][0];
    const fin = datos.stops[d.stops[d.stops.length - 1][0]][0];
    return [dir, ini + " → " + fin];
  });
  fillSelect(el.sentido, sentidos, "Selecciona el sentido…");
  if (sentidos.length === 1) { el.sentido.value = sentidos[0][0]; el.sentido.dispatchEvent(new Event("change")); }
});

el.sentido.addEventListener("change", () => {
  resetDesde(4);
  if (!datos || !el.linea.value || el.sentido.value === "") return;
  const stops = datos.routes[el.linea.value].dirs[el.sentido.value].stops;
  const paradas = stops.map(([sid]) => [sid, datos.stops[sid][0]]);
  fillSelect(el.origen, paradas, "Parada de origen…");
  fillSelect(el.destino, paradas, "Parada de destino…");
});

/* ---------- Cálculo de km ---------- */

// Metros a lo largo del trazado entre origen y destino dentro del sentido elegido.
// El destino debe ir DESPUÉS del origen en ese sentido.
function calcularKm(rutaId, dir, origen, destino) {
  const ruta = datos.routes[rutaId];
  const lista = ruta.dirs[dir].stops;
  const i = lista.findIndex(([s]) => s === origen);
  const j = origen === destino && ruta.circular
    ? lista.map(([s]) => s).lastIndexOf(destino)
    : lista.findIndex(([s]) => s === destino);
  if (i < 0 || j < 0) return null;
  if (j < i && ruta.circular) {
    const total = lista[lista.length - 1][1] - lista[0][1];
    return (total - lista[i][1] + lista[j][1]) / 1000;
  }
  if (j <= i) return null;
  return (lista[j][1] - lista[i][1]) / 1000;
}

function actualizarKm() {
  kmActual = null;
  el.resultado.hidden = true;
  mostrarError("");
  if (!datos || !el.linea.value || el.sentido.value === "" || !el.origen.value || !el.destino.value) return;

  if (el.origen.value === el.destino.value && !datos.routes[el.linea.value].circular) {
    mostrarError("El origen y el destino son la misma parada.");
    return;
  }
  const km = calcularKm(el.linea.value, el.sentido.value, el.origen.value, el.destino.value);
  if (km === null) {
    mostrarError("En este sentido el destino queda antes que el origen. Cambia el sentido o intercambia las paradas.");
    return;
  }
  kmActual = km;
  const aprox = datos.aprox || !!datos.routes[el.linea.value].dirs[el.sentido.value].aprox;
  el.kmTexto.textContent = (aprox ? "≈ " : "") + km.toFixed(1).replace(".", ",") + " km";
  el.kmNota.textContent = aprox
    ? "aproximado: suma de distancias entre paradas"
    : "siguiendo el trazado de la línea";
  el.resultado.hidden = false;
}
el.origen.addEventListener("change", actualizarKm);
el.destino.addEventListener("change", actualizarKm);

/* ---------- Almacenamiento ---------- */

const leer = () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; } catch { return []; } };
const escribir = (v) => localStorage.setItem(STORAGE_KEY, JSON.stringify(v));

el.form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  mostrarError("");

  const cfg = (CIUDADES[el.tipo.value] || []).find((c) => c.nombre === el.ciudad.value);
  let km = kmActual;

  const esOtra = el.linea.value === OTRA;
  if (cfg && cfg.data && datos && !esOtra) {
    if (!el.linea.value || el.sentido.value === "" || !el.origen.value || !el.destino.value)
      return mostrarError("Elige línea, sentido, origen y destino.");
    if (km === null) return mostrarError("No se ha podido calcular la distancia con esas paradas.");
  } else {
    km = el.kmManual.value === "" ? null : parseFloat(el.kmManual.value);
  }
  if (cfg && cfg.otro && !el.otroTexto.value.trim()) return mostrarError("Indica qué transporte es.");
  if (esOtra && !el.lineaOtra.value.trim()) return mostrarError("Indica qué línea es.");

  const ruta = datos && el.linea.value && !esOtra ? datos.routes[el.linea.value] : null;
  const registro = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    sync: false,
    fecha: el.fecha.value,
    tipo: el.tipo.value,
    ciudad: cfg && cfg.otro ? el.ciudad.value + ": " + el.otroTexto.value.trim() : el.ciudad.value,
    lineaCodigo: ruta ? ruta.code : (esOtra ? el.lineaOtra.value.trim() : ""),
    lineaNombre: ruta ? ruta.name : "",
    color: ruta ? "#" + ruta.color : "",
    colorTexto: ruta ? "#" + (ruta.textColor || "FFFFFF") : "",
    origen: ruta && el.origen.value ? datos.stops[el.origen.value][0] : "",
    destino: ruta && el.destino.value ? datos.stops[el.destino.value][0] : "",
    km: km === null ? null : Math.round(km * 10) / 10,
    aprox: !!(ruta && (datos.aprox || datos.routes[el.linea.value].dirs[el.sentido.value].aprox)),
    espera: parseInt(el.espera.value, 10) || 0,
    trayecto: parseInt(el.trayecto.value, 10) || 0,
  };

  const lista = leer();
  lista.push(registro);
  escribir(lista);

  // Limpia lo específico del trayecto; conserva la fecha.
  el.tipo.value = ""; resetDesde(1);
  el.espera.value = ""; el.trayecto.value = "";
  render();
  sincronizar();
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
});

/* ---------- Sincronización con Google Sheets ---------- */

const CFG_KEY = "trayectos.sheets.v1";
const ui = {
  estado: $("syncEstado"), sync: $("sincronizarAhora"), url: $("sheetUrl"),
  token: $("sheetToken"), probar: $("probarConexion"), msg: $("cfgMsg"), ajustes: $("ajustes"),
};
let sincronizando = false;
let ultimoError = "";

const cfgLeer = () => { try { return JSON.parse(localStorage.getItem(CFG_KEY)) || {}; } catch { return {}; } };
const cfgGuardar = (c) => localStorage.setItem(CFG_KEY, JSON.stringify(c));
const configurado = () => { const c = cfgLeer(); return !!(c.url && c.token); };

// Los trayectos guardados antes de existir la sincronización NO se suben:
// se marcan con sync = "no" y no vuelven a considerarse.
function migrar() {
  const lista = leer();
  let cambio = false;
  lista.forEach((t) => { if (t.sync === undefined) { t.sync = "no"; cambio = true; } });
  if (cambio) escribir(lista);
}

function textoError(e) {
  const m = String((e && e.message) || e);
  if (m === "token") return "Token incorrecto.";
  if (m === "respuesta") return "Google no devolvió lo esperado: revisa la URL y que el acceso sea «Cualquier persona».";
  if (m === "datos") return "Faltan datos en el trayecto.";
  if (e && (e.name === "AbortError" || e.name === "TypeError")) return "Sin conexión con Google; se reintentará solo.";
  return "Error: " + m;
}

// Envío como texto plano (petición simple): evita el preflight CORS, que Apps Script no admite.
async function llamar(cfg, payload) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const res = await fetch(cfg.url, { method: "POST", body: JSON.stringify({ ...payload, token: cfg.token }), signal: ctrl.signal });
    let data;
    try { data = await res.json(); } catch { throw new Error("respuesta"); }
    if (!data || data.ok !== true) throw new Error((data && data.error) || "respuesta");
    return data;
  } finally { clearTimeout(timer); }
}

function marcarSincronizado(id) {
  const lista = leer();                                  // se relee: puede haber cambiado durante la espera
  const t = lista.find((x) => String(x.id) === String(id));
  if (t) { t.sync = true; escribir(lista); }
}

async function sincronizar() {
  if (sincronizando || !configurado()) { render(); return; }
  sincronizando = true;
  ultimoError = "";
  pintarEstado();
  try {
    const cfg = cfgLeer();
    const pendientes = leer().filter((t) => t.sync === false);
    for (const t of pendientes) {
      await llamar(cfg, { id: String(t.id), fecha: t.fecha, tipo: t.tipo, ciudad: t.ciudad,
        lineaCodigo: t.lineaCodigo, lineaNombre: t.lineaNombre, origen: t.origen, destino: t.destino,
        km: t.km, espera: t.espera, trayecto: t.trayecto });
      marcarSincronizado(t.id);
    }
  } catch (e) {
    ultimoError = textoError(e);
  } finally {
    sincronizando = false;
    render();
  }
}

function pintarEstado(lista) {
  const l = lista || leer();
  if (!configurado() && !ui.ajustes.dataset.abiertoAuto) {
    ui.ajustes.open = true;
    ui.ajustes.dataset.abiertoAuto = "1";   // solo lo forzamos una vez; si el usuario lo cierra, se respeta
  }
  const pend = l.filter((t) => t.sync === false).length;
  let txt, cls = "";
  if (!configurado()) {
    txt = pend ? `Sin configurar · ${pend} trayecto(s) esperando` : "Sin configurar: los trayectos solo se guardan en este iPhone.";
  } else if (sincronizando) {
    txt = "Sincronizando…";
  } else if (ultimoError) {
    txt = ultimoError + (pend ? ` (${pend} pendiente${pend > 1 ? "s" : ""})` : ""); cls = "warn";
  } else if (pend) {
    txt = `${pend} pendiente${pend > 1 ? "s" : ""} de enviar`; cls = "warn";
  } else {
    txt = "Todo sincronizado ✓"; cls = "ok";
  }
  ui.estado.textContent = txt;
  ui.estado.className = cls;
}

function guardarAjustes() {
  const url = ui.url.value.trim(), token = ui.token.value.trim();
  cfgGuardar({ url, token });
  ui.msg.textContent = url && !url.startsWith("https://script.google.com/")
    ? "La URL debería empezar por https://script.google.com/" : "";
  ui.msg.className = "warn";
  sincronizar();
}
["input", "change"].forEach((ev) => {
  ui.url.addEventListener(ev, guardarAjustes);
  ui.token.addEventListener(ev, guardarAjustes);
});
ui.sync.addEventListener("click", sincronizar);

ui.probar.addEventListener("click", async () => {
  const cfg = { url: ui.url.value.trim(), token: ui.token.value.trim() };
  if (!cfg.url || !cfg.token) { ui.msg.textContent = "Rellena la URL y el token."; ui.msg.className = "warn"; return; }
  cfgGuardar(cfg);
  ui.msg.textContent = "Probando…"; ui.msg.className = "";
  try { await llamar(cfg, { accion: "ping" }); ui.msg.textContent = "Conexión correcta ✓"; ui.msg.className = "ok"; sincronizar(); }
  catch (e) { ui.msg.textContent = textoError(e); ui.msg.className = "warn"; }
});

window.addEventListener("online", sincronizar);
document.addEventListener("visibilitychange", () => { if (!document.hidden) sincronizar(); });

/* ---------- Historial y resumen ---------- */

function render() {
  const lista = leer().sort((a, b) => b.fecha.localeCompare(a.fecha) || String(b.id).localeCompare(String(a.id)));
  pintarEstado(lista);

  const km = lista.reduce((s, t) => s + (t.km || 0), 0);
  const espera = lista.reduce((s, t) => s + t.espera, 0);
  $("sViajes").textContent = lista.length;
  $("sKm").textContent = km.toFixed(1).replace(".", ",");
  $("sEspera").textContent = espera;

  if (!lista.length) {
    el.historial.innerHTML = '<div class="hint">Aún no hay trayectos guardados.</div>';
    return;
  }
  el.historial.innerHTML = lista.map((t) => {
    const fecha = new Date(t.fecha + "T00:00:00").toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });
    const badge = t.lineaCodigo
      ? `<span class="badge" style="background:${escapeHtml(t.color || "#0b5fff")};color:${escapeHtml(t.colorTexto || "#fff")}">${escapeHtml(t.lineaCodigo)}</span>` : "";
    const ruta = t.origen ? `${escapeHtml(t.origen)} → ${escapeHtml(t.destino)}` : escapeHtml(t.tipo);
    const kmTxt = t.km === null ? "km sin indicar" : (t.aprox ? "≈ " : "") + t.km.toFixed(1).replace(".", ",") + " km";
    const marca = t.sync === true ? ' · <span class="ok">✓ en Sheets</span>'
                : t.sync === false ? ' · <span class="warn">⏳ pendiente</span>' : "";
    return `<div class="trip">
      <div class="trip-head"><span>${badge}${escapeHtml(t.ciudad)}</span><span>${fecha}</span></div>
      <div class="trip-sub">${ruta}</div>
      <div class="trip-sub">${kmTxt} · espera ${t.espera} min · trayecto ${t.trayecto} min${marca}</div>
      <div class="actions"><span></span>
        <button class="ghost danger" data-del="${t.id}" type="button">Eliminar</button></div>
    </div>`;
  }).join("");
}

el.historial.addEventListener("click", (ev) => {
  const id = ev.target.dataset && ev.target.dataset.del;
  if (!id) return;
  if (confirm("¿Eliminar este trayecto?")) {
    escribir(leer().filter((t) => String(t.id) !== id));
    render();
  }
});

$("borrarTodo").addEventListener("click", () => {
  if (leer().length && confirm("¿Borrar TODOS los trayectos? No se puede deshacer.")) {
    escribir([]); render();
  }
});

$("exportar").addEventListener("click", () => {
  const lista = leer();
  if (!lista.length) return alert("No hay trayectos que exportar.");
  const cab = ["fecha", "tipo", "ciudad", "linea", "origen", "destino", "km", "espera_min", "trayecto_min"];
  const q = (v) => '"' + String(v ?? "").replace(/"/g, '""') + '"';
  const filas = lista.map((t) =>
    [t.fecha, t.tipo, t.ciudad, t.lineaCodigo, t.origen, t.destino, t.km ?? "", t.espera, t.trayecto].map(q).join(","));
  const blob = new Blob(["\ufeff" + [cab.join(","), ...filas].join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "trayectos.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});

/* ---------- Arranque ---------- */

el.fecha.value = hoyLocal();
migrar();
{ const c = cfgLeer(); ui.url.value = c.url || ""; ui.token.value = c.token || ""; }
render();
sincronizar();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
