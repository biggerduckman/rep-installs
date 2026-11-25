/* Rep Installs service worker (v5). Network-first so iPhones pick up new builds. */
const VERSION = "installs-v5";

self.addEventListener("install", event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith("installs-") && k !== VERSION).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith((async () => {
    try {
      return await fetch(event.request, { cache: "no-store" });
    } catch (err) {
      const cache = await caches.open(VERSION);
      const hit = await cache.match(event.request);
      if (hit) return hit;
      throw err;
    }
  })());
});
