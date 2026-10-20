/* SportsPred offline support: pages and assets come from the cache when there's no connection.
   Data (data/*.json) and pages are network-first, so you always see the latest when online. */
const VERSION = "sportspred-v4";
const CORE = ["./", "index.html", "competition.html", "how.html", "404.html", "assets/app.css", "assets/app.js",
  "assets/index.js", "assets/competition.js", "assets/how.js", "assets/notfound.js", "assets/team.js", "team.html", "assets/icon.svg", "assets/icon-192.png", "manifest.webmanifest"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// mark a cached answer so the page can say it's showing offline data
async function fromCache(req) {
  const hit = await caches.match(req, { ignoreSearch: req.mode === "navigate" });
  if (!hit) return Response.error();
  const headers = new Headers(hit.headers);
  headers.set("X-SportsPred-Cache", "1");
  return new Response(await hit.blob(), { status: hit.status, statusText: hit.statusText, headers });
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameSite = url.origin === location.origin;
  const fresh = req.mode === "navigate" || (sameSite && (url.pathname.includes("/data/") || /\.(html|js|css)$/.test(url.pathname)));
  if (fresh) {  // network first, keep a copy, fall back to the copy
    // always check with the server (a cheap "not modified" when nothing changed), never the HTTP cache
    e.respondWith(fetch(sameSite ? new Request(req.url, { cache: "no-cache", credentials: "same-origin" }) : req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => fromCache(req)));
  } else {      // fonts, Chart.js, icons: cache first
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
