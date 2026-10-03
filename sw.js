// Service worker: cachea la app y los datos para que funcione sin conexion.
// Al cambiar cualquier archivo, sube el numero de VERSION para forzar la actualizacion.
const VERSION = "v17";
const CACHE = "trayectos-" + VERSION;
const ARCHIVOS = [
  "./", "index.html", "app.js", "manifest.json",
  "icon-192.png", "icon-512.png",
  "data/bahia-cadiz.json", "data/trambahia.json", "data/cercanias-cadiz.json", "data/urbano-cadiz.json", "data/madrid-metro.json", "data/cercanias-madrid.json", "data/tmb-barcelona-metro.json", "data/tmb-barcelona-bus.json", "data/rodalies-catalunya.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  if (new URL(e.request.url).origin !== self.location.origin) return;   // Google Sheets, etc.: sin caché
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copia = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copia));
      return res;
    }).catch(() => caches.match("index.html")))
  );
});
