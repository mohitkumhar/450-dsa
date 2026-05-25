const CACHE_VERSION = "pwa-v1";
const OFFLINE_URL = "/static/offline.html";
const PRECACHE_URLS = [
  OFFLINE_URL,
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.svg",
  "/static/icons/icon-512.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_VERSION)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

function isNavigationRequest(request) {
  return request.mode === "navigate";
}

function isExcludedRequest(url, request) {
  if (request.method !== "GET") {
    return true;
  }

  return url.pathname.startsWith("/sync") ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/update_question") ||
    url.pathname.startsWith("/sync_platforms");
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin || isExcludedRequest(url, request)) {
    return;
  }

  if (isNavigationRequest(request)) {
    event.respondWith(
      fetch(request)
        .then((response) => response)
        .catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) {
          return cached;
        }

        return fetch(request).then((response) => {
          if (!response || response.status !== 200) {
            return response;
          }

          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
          return response;
        });
      })
    );
  }
});
