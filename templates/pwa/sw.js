const CACHE_NAME = 'caisse-pwa-v2';
const OFFLINE_URLS = [
  // Ne pas mettre '/' ni '/gestion-caisses/' pour éviter d'intercepter les navigations
  '/static/jazzmin/overrides.css'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await cache.addAll(OFFLINE_URLS);
      // Prendre immédiatement le contrôle après installation
      await self.skipWaiting();
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Stratégie network-first pour les navigations (HTML pages)
  if (request.mode === 'navigate' || (request.destination === 'document')) {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(request, { cache: 'no-store' });
          return networkResponse;
        } catch (e) {
          const cache = await caches.open(CACHE_NAME);
          const cached = await cache.match('/gestion-caisses/login/');
          return cached || Response.error();
        }
      })()
    );
    return;
  }

  // Pour les assets: cache-first puis réseau en secours
  event.respondWith(
    (async () => {
      const cached = await caches.match(request);
      if (cached) return cached;
      try {
        const resp = await fetch(request);
        return resp;
      } catch (e) {
        return Response.error();
      }
    })()
  );
});


