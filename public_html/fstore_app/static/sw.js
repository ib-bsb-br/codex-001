const CACHE_NAME = 'memor-cache-v1.4';
const SHELL = [
  '/?b=public',
  '/manifest.json',
  '/favicon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => (key !== CACHE_NAME ? caches.delete(key) : Promise.resolve()))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/boards/') && event.request.method === 'GET') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(event.request);
      const fetchPromise = fetch(event.request).then((response) => {
        if (response && (response.status === 200 || response.status === 304)) {
          cache.put(event.request, response.clone());
        }
        return response;
      }).catch(() => cached);
      return cached || fetchPromise;
    })());
    return;
  }

  if (event.request.method === 'GET') {
    event.respondWith((async () => {
      try {
        const network = await fetch(event.request);
        const cache = await caches.open(CACHE_NAME);
        cache.put(event.request, network.clone());
        return network;
      } catch (err) {
        const cache = await caches.open(CACHE_NAME);
        const cached = await cache.match(event.request);
        return cached || new Response('<!doctype html><meta charset="utf-8"><title>Offline</title><h1>Offline</h1><p>The app is offline. Retry when back online.</p>', {
          headers: { 'Content-Type': 'text/html; charset=utf-8' }
        });
      }
    })());
  }
});
