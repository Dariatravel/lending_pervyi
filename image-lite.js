(() => {
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const saveData = Boolean(connection && connection.saveData);
  const effectiveType = connection && typeof connection.effectiveType === "string" ? connection.effectiveType : "";
  const constrainedNetwork = saveData || /(^slow-2g$|^2g$|^3g$)/i.test(effectiveType);
  const YANDEX_MEDIA_RE = /^https:\/\/storage\.yandexcloud\.net\/abhazbereg-media\/media\//;

  const isYandexMedia = (src) => {
    try {
      const url = new URL(src, window.location.href);
      return YANDEX_MEDIA_RE.test(url.href);
    } catch {
      return false;
    }
  };

  const enhanceImage = (img, index) => {
    if (!img || img.dataset.imageLite === "done") return;

    const original = img.currentSrc || img.getAttribute("src") || "";
    if (!original || !isYandexMedia(original)) return;

    img.dataset.imageLite = "done";
    img.dataset.originalSrc = original;
    img.decoding = "async";
    img.loading = img.loading || (index < 2 ? "eager" : "lazy");
    img.fetchPriority = index < 2 ? "high" : "low";
  };

  const run = () => {
    document.documentElement.classList.toggle("network-lite", constrainedNetwork);
    document.querySelectorAll("img").forEach(enhanceImage);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run, { once: true });
  } else {
    run();
  }
})();
