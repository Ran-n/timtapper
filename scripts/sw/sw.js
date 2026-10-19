// The site's service worker: keeps this build's files and serves them from there, so a repeat visit opens without
// asking the host (GitHub Pages lets browsers keep a file only 10 minutes, then every one is asked for again).
//
// scripts/build_web.py writes BUILD above this: the build's id (a digest of its files) and the files to keep. Every
// file the page asks for comes from this build's cache, the page itself too, so one visit never mixes two builds.
// A new build's worker fills its own cache as it installs, then waits; the next visit's page has it take over and
// reloads once (register.js), from that cache.
"use strict";

const SITE = "timtapper-site-"; // never another cache of the origin (Python's snapshot keeps its own)
const CACHE = `${SITE}${BUILD.id}`;
const INDEX = new URL("./", self.location).href;
const PAGES = new Set([INDEX, new URL("index.html", self.location).href]);

self.addEventListener("install", (event) => {
  // no-cache: the browser may still hold the previous build's files; an unchanged one costs a 304, not a download
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(BUILD.files.map((f) => new Request(f, { cache: "no-cache" }))))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key.startsWith(SITE) && key !== CACHE) await caches.delete(key);
      }
      await self.clients.claim();
    })()
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "activate") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  // the site's own files; the CDNs' (Pyodide, CanvasKit) are versioned and kept by the browser for a year
  if (request.method !== "GET" || url.origin !== self.location.origin || !url.href.startsWith(INDEX)) return;
  const page = request.mode === "navigate";
  if (page && !PAGES.has(url.origin + url.pathname)) return;
  event.respondWith(respond(request, page));
});

async function respond(request, page) {
  const cache = await caches.open(CACHE);
  const kept = await cache.match(page ? INDEX : request);
  if (kept) return kept;
  const response = await fetch(request);
  // what the build didn't list but the app asks for (a flag, a portrait): kept as this build's from now on
  if (!page && response.ok && response.type === "basic") await cache.put(request, response.clone());
  return response;
}
