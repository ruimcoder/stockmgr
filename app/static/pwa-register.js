(function () {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // Ignore registration failures to keep the app usable in all browsers.
    });
  });
})();
