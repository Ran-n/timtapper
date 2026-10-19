// Puts the site's service worker (sw.js) in place. scripts/build_web.py writes window.TIMTAPPER_SW before this: the
// worker's URL, and the channel and message the app says it's ready with.
//
// Registered only once the app has started: installing fetches the build's files, and on a first visit the page is
// fetching those same files. A worker that installed on an earlier visit and is waiting (a new build) takes over as
// the page opens, which then reloads once, from the new build's cache.
(() => {
  "use strict";
  const config = window.TIMTAPPER_SW;
  if (!config || !("serviceWorker" in navigator)) return;
  const sw = navigator.serviceWorker;

  sw.getRegistration().then((registration) => {
    if (!registration || !registration.waiting || !sw.controller) return;
    sw.addEventListener("controllerchange", () => location.reload(), { once: true });
    registration.waiting.postMessage("activate");
    console.log("timtapper: a new version is ready, reloading");
  });

  function register() {
    sw.register(config.url).then(
      () => console.log("timtapper: service worker registered"),
      (error) => console.error("timtapper: service worker not registered:", error)
    );
  }

  if (!("BroadcastChannel" in window)) return;
  const channel = new BroadcastChannel(config.channel);
  channel.onmessage = (ev) => {
    if (ev.data && ev.data.type === config.ready) {
      channel.close();
      register();
    }
  };
})();
