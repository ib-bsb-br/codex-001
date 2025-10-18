const VERSION = '__APP_VERSION__';
const CACHE_NAME = `fstore-cache-${VERSION}`;
const SHELL = [
  '/',
  '/?b=public',
  '/manifest.json',
  '/favicon.svg',
  `/static/app.css?v=${VERSION}`,
  `/static/app.js?v=${VERSION}`,
  `/static/files.js?v=${VERSION}`,
  `/static/dashboard.js?v=${VERSION}`,
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)).catch(() => Promise.resolve())
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((key) => (key !== CACHE_NAME ? caches.delete(key) : Promise.resolve())))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (event.request.method !== 'GET') return;

  if (url.pathname.startsWith('/api/boards/')) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(event.request);
      try {
        const network = await fetch(event.request);
        if (network && (network.status === 200 || network.status === 304)) {
          cache.put(event.request, network.clone());
        }
        return network;
      } catch (err) {
        return cached || new Response(JSON.stringify({ error: 'offline' }), {
          headers: { 'Content-Type': 'application/json' },
          status: 503,
        });
      }
    })());
    return;
  }

  if (SHELL.includes(url.pathname) || url.pathname.startsWith('/static/')) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(event.request);
      if (cached) return cached;
      try {
        const network = await fetch(event.request);
        cache.put(event.request, network.clone());
        return network;
      } catch (err) {
        return cached || Response.error();
      }
    })());
    return;
  }

  event.respondWith((async () => {
    try {
      const network = await fetch(event.request);
      return network;
    } catch (err) {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(event.request);
      if (cached) return cached;
      return new Response('<!doctype html><meta charset="utf-8"><title>Offline</title><h1>Offline</h1><p>The hub is offline. Retry when back online.</p>', {
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      });
    }
  })());
});
