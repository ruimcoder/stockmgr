(function () {
  const lookupForm = document.getElementById("barcode-lookup-form");
  if (!lookupForm) {
    return;
  }

  const barcodeInput = document.getElementById("lookup-barcode-input");
  const startButton = document.getElementById("start-camera-scan");
  const stopButton = document.getElementById("stop-camera-scan");
  const video = document.getElementById("barcode-camera-preview");
  const status = document.getElementById("barcode-scan-status");

  let detector = null;
  let stream = null;
  let timerHandle = null;

  const setStatus = (text) => {
    status.textContent = text;
  };

  const stopScanner = () => {
    if (timerHandle) {
      window.clearInterval(timerHandle);
      timerHandle = null;
    }
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
    if (video) {
      video.srcObject = null;
    }
    setStatus(status.dataset.idle);
  };

  const processFrame = async () => {
    if (!detector || !video || video.readyState < 2) {
      return;
    }
    try {
      const codes = await detector.detect(video);
      if (!codes.length) {
        return;
      }
      const rawValue = codes[0].rawValue;
      if (!rawValue) {
        return;
      }
      barcodeInput.value = rawValue;
      setStatus(status.dataset.detected);
      stopScanner();
      lookupForm.requestSubmit();
    } catch (_error) {
      // Keep scanning; intermittent detection errors are expected on some devices.
    }
  };

  const startScanner = async () => {
    if (!("BarcodeDetector" in window)) {
      setStatus(status.dataset.unsupported);
      return;
    }

    try {
      detector = new window.BarcodeDetector({
        formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"],
      });
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      video.srcObject = stream;
      await video.play();
      setStatus(status.dataset.scanning);
      timerHandle = window.setInterval(processFrame, 350);
    } catch (_error) {
      stopScanner();
      setStatus(status.dataset.permissionError);
    }
  };

  startButton.addEventListener("click", startScanner);
  stopButton.addEventListener("click", stopScanner);
})();

