(function () {
  const i18n = document.getElementById("device-check-i18n");
  if (!i18n) {
    return;
  }

  const supportedText = i18n.dataset.supported || "Supported";
  const notSupportedText = i18n.dataset.notSupported || "Not supported";

  const setCapability = (idSuffix, supported, detail) => {
    const statusNode = document.getElementById(`cap-${idSuffix}`);
    const detailNode = document.getElementById(`detail-${idSuffix}`);
    if (!statusNode || !detailNode) {
      return;
    }
    statusNode.textContent = supported ? supportedText : notSupportedText;
    statusNode.className = supported ? "text-success fw-semibold" : "text-danger fw-semibold";
    detailNode.textContent = detail;
  };

  const standaloneMode =
    window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  const hasMediaDevices = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  const hasBarcodeDetector = "BarcodeDetector" in window;
  const hasServiceWorker = "serviceWorker" in navigator;

  setCapability("secure-context", window.isSecureContext, window.isSecureContext ? "HTTPS/localhost" : "HTTP");
  setCapability(
    "media-devices",
    hasMediaDevices,
    hasMediaDevices ? "getUserMedia available" : "Camera APIs unavailable"
  );
  setCapability(
    "barcode-detector",
    hasBarcodeDetector,
    hasBarcodeDetector ? "Native detector available" : "Fallback mode recommended"
  );
  setCapability(
    "service-worker",
    hasServiceWorker,
    hasServiceWorker ? "PWA offline support available" : "PWA installability reduced"
  );
  setCapability(
    "standalone",
    standaloneMode,
    standaloneMode ? "Running as installed app" : "Running in browser tab"
  );

  const userAgentNode = document.getElementById("detail-user-agent");
  if (userAgentNode) {
    userAgentNode.textContent = navigator.userAgent;
  }
})();
