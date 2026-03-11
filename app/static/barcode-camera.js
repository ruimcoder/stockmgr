(function () {
  const lookupForm = document.getElementById("barcode-lookup-form");
  if (!lookupForm) {
    return;
  }

  const barcodeInput = document.getElementById("lookup-barcode-input");
  const startButton = document.getElementById("start-camera-scan");
  const stopButton = document.getElementById("stop-camera-scan");
  const video = document.getElementById("barcode-camera-preview");
  const fallbackContainer = document.getElementById("barcode-fallback-reader-container");
  const status = document.getElementById("barcode-scan-status");

  const supportsMediaDevices = !!(
    navigator.mediaDevices && navigator.mediaDevices.getUserMedia
  );
  const supportsBarcodeDetector = "BarcodeDetector" in window;
  const supportsHtml5Qrcode = typeof window.Html5Qrcode === "function";

  const preferredFormats = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

  let detector = null;
  let stream = null;
  let animationFrameHandle = null;
  let html5Scanner = null;
  let usingFallback = false;
  let hasDetectedValue = false;
  let isStarting = false;

  const setStatus = (text) => {
    if (!status) {
      return;
    }
    status.textContent = text;
  };

  const setControls = (scanning) => {
    if (startButton) {
      startButton.disabled = scanning || isStarting;
    }
    if (stopButton) {
      stopButton.disabled = !scanning;
    }
  };

  const setFallbackVisibility = (visible) => {
    if (!fallbackContainer) {
      return;
    }
    fallbackContainer.classList.toggle("d-none", !visible);
  };

  const stopNativeScanner = () => {
    if (animationFrameHandle) {
      window.cancelAnimationFrame(animationFrameHandle);
      animationFrameHandle = null;
    }
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
    if (video) {
      video.srcObject = null;
    }
    detector = null;
  };

  const stopFallbackScanner = async () => {
    if (!html5Scanner) {
      return;
    }
    try {
      await html5Scanner.stop();
    } catch (_error) {
      // Ignore stop race conditions when scanner has already stopped.
    }
    try {
      await html5Scanner.clear();
    } catch (_error) {
      // Ignore clear errors to keep stop flow resilient.
    }
    html5Scanner = null;
    usingFallback = false;
    setFallbackVisibility(false);
  };

  const stopScanner = async ({ preserveStatus = false } = {}) => {
    stopNativeScanner();
    await stopFallbackScanner();
    hasDetectedValue = false;
    setControls(false);
    if (!preserveStatus) {
      setStatus(status.dataset.idle);
    }
  };

  const submitDetectedBarcode = async (rawValue) => {
    if (!rawValue || hasDetectedValue) {
      return;
    }
    hasDetectedValue = true;
    barcodeInput.value = rawValue;
    setStatus(status.dataset.detected);
    await stopScanner({ preserveStatus: true });
    lookupForm.requestSubmit();
  };

  const processNativeFrame = async () => {
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
      await submitDetectedBarcode(rawValue);
    } catch (_error) {
      // Keep scanning; intermittent detection errors are expected on some devices.
    }
  };

  const nativeScanLoop = async () => {
    await processNativeFrame();
    if (stream) {
      animationFrameHandle = window.requestAnimationFrame(() => {
        void nativeScanLoop();
      });
    }
  };

  const queryPermissionDenied = async () => {
    if (!navigator.permissions || !navigator.permissions.query) {
      return false;
    }
    try {
      const result = await navigator.permissions.query({ name: "camera" });
      return result.state === "denied";
    } catch (_error) {
      return false;
    }
  };

  const startNativeScanner = async () => {
    const supportedFormats = await window.BarcodeDetector.getSupportedFormats?.();
    let selectedFormats =
      supportedFormats && supportedFormats.length
        ? preferredFormats.filter((format) => supportedFormats.includes(format))
        : preferredFormats;
    if (supportedFormats && supportedFormats.length && !selectedFormats.length) {
      selectedFormats = supportedFormats;
    }
    detector = new window.BarcodeDetector({
      formats: selectedFormats.length ? selectedFormats : preferredFormats,
    });
    const nativeConstraints = [
      {
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      },
      {
        video: {
          facingMode: "environment",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      },
      {
        video: {
          facingMode: { ideal: "user" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      },
      { video: true, audio: false },
    ];
    let streamError = null;
    for (const constraints of nativeConstraints) {
      try {
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        break;
      } catch (error) {
        streamError = error;
      }
    }
    if (!stream) {
      throw streamError || new Error("Unable to access camera stream.");
    }
    video.srcObject = stream;
    await video.play();
    setStatus(status.dataset.scanning);
    setControls(true);
    animationFrameHandle = window.requestAnimationFrame(() => {
      void nativeScanLoop();
    });
  };

  const startFallbackScanner = async () => {
    if (!supportsHtml5Qrcode) {
      setStatus(status.dataset.unsupported);
      return;
    }
    const formatsEnum = window.Html5QrcodeSupportedFormats || {};
    const formats = ["EAN_13", "EAN_8", "UPC_A", "UPC_E", "CODE_128"]
      .map((key) => formatsEnum[key])
      .filter(Boolean);
    usingFallback = true;
    setFallbackVisibility(true);
    const scannerConfig = {
      fps: 10,
      qrbox: { width: 280, height: 160 },
    };
    const onDecode = (decodedText) => {
      void submitDetectedBarcode(decodedText);
    };
    const cameraCandidates = [{ facingMode: "environment" }, { facingMode: "user" }];
    try {
      const devices = await window.Html5Qrcode.getCameras();
      for (const device of devices || []) {
        if (device && device.id) {
          cameraCandidates.push(device.id);
        }
      }
    } catch (_error) {
      // Keep default candidates when device listing is unavailable.
    }
    let fallbackError = null;
    for (const cameraConfig of cameraCandidates) {
      const scanner = new window.Html5Qrcode("barcode-fallback-reader", {
        formatsToSupport: formats.length ? formats : undefined,
        verbose: false,
      });
      try {
        await scanner.start(cameraConfig, scannerConfig, onDecode, () => {});
        html5Scanner = scanner;
        fallbackError = null;
        break;
      } catch (error) {
        fallbackError = error;
        try {
          await scanner.clear();
        } catch (_clearError) {
          // Ignore cleanup errors between attempts.
        }
      }
    }
    if (!html5Scanner) {
      usingFallback = false;
      setFallbackVisibility(false);
      throw fallbackError || new Error("Unable to start compatibility scanner.");
    }
    setStatus(status.dataset.fallbackScanning);
    setControls(true);
  };

  const startScanner = async () => {
    if (isStarting || stream || usingFallback) {
      return;
    }
    if (!window.isSecureContext) {
      setStatus(status.dataset.secureContextRequired);
      return;
    }
    if (!supportsMediaDevices) {
      setStatus(status.dataset.mediaUnsupported);
      return;
    }
    if (await queryPermissionDenied()) {
      setStatus(status.dataset.permissionDenied);
      return;
    }

    isStarting = true;
    setControls(false);
    try {
      if (supportsBarcodeDetector) {
        try {
          await startNativeScanner();
        } catch (_nativeError) {
          stopNativeScanner();
          await startFallbackScanner();
        }
      } else {
        await startFallbackScanner();
      }
    } catch (_error) {
      await stopScanner();
      setStatus(status.dataset.permissionError);
    } finally {
      isStarting = false;
      if (!stream && !usingFallback) {
        setControls(false);
      }
    }
  };

  setControls(false);
  setFallbackVisibility(false);
  setStatus(status.dataset.idle);

  startButton.addEventListener("click", () => {
    void startScanner();
  });
  stopButton.addEventListener("click", () => {
    void stopScanner();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      void stopScanner();
    }
  });
  window.addEventListener("pagehide", () => {
    void stopScanner();
  });
})();

