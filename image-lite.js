(() => {
  const SUPABASE_OBJECT_RE = /\/storage\/v1\/object\/public\/site-media\//;
  const SUPABASE_RENDER_PATH = "/storage/v1/render/image/public/site-media/";
  const WIDTHS = [320, 480, 640, 800, 960, 1200, 1440];
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const saveData = Boolean(connection && connection.saveData);
  const effectiveType = connection && typeof connection.effectiveType === "string" ? connection.effectiveType : "";
  const constrainedNetwork = saveData || /(^slow-2g$|^2g$|^3g$)/i.test(effectiveType);
  const maxWidth = constrainedNetwork ? 800 : 1440;
  const quality = constrainedNetwork ? 58 : 72;

  const canOptimize = (url) => SUPABASE_OBJECT_RE.test(url) && !url.includes("/storage/v1/render/image/");

  const optimizedUrl = (src, width) => {
    try {
      const url = new URL(src, window.location.href);
      if (!canOptimize(url.href)) return "";

      const path = url.pathname.split("/storage/v1/object/public/site-media/")[1];
      if (!path) return "";

      url.pathname = SUPABASE_RENDER_PATH + path;
      url.searchParams.set("width", String(width));
      url.searchParams.set("quality", String(quality));
      url.searchParams.set("resize", "contain");
      url.searchParams.set("format", "webp");
      return url.href;
    } catch {
      return "";
    }
  };

  const desiredWidth = (img) => {
    const box = img.getBoundingClientRect();
    const cssWidth = Math.max(box.width, img.width || 0, 320);
    const dpr = Math.min(window.devicePixelRatio || 1, constrainedNetwork ? 1.5 : 2);
    const target = Math.ceil(cssWidth * dpr);
    return WIDTHS.find((width) => width >= target) || maxWidth;
  };

  const makeSrcset = (src) =>
    WIDTHS
      .filter((width) => width <= maxWidth)
      .map((width) => `${optimizedUrl(src, width)} ${width}w`)
      .filter((entry) => !entry.startsWith(" "))
      .join(", ");

  const enhanceImage = (img, index) => {
    if (!img || img.dataset.imageLite === "done") return;

    const original = img.currentSrc || img.getAttribute("src") || "";
    if (!original || !canOptimize(original)) return;

    img.dataset.imageLite = "done";
    img.dataset.originalSrc = original;
    img.decoding = "async";
    img.loading = img.loading || (index < 2 ? "eager" : "lazy");
    img.fetchPriority = index < 2 ? "high" : "low";
    img.sizes = img.sizes || "(max-width: 760px) 92vw, (max-width: 1200px) 46vw, 420px";

    const srcset = makeSrcset(original);
    const src = optimizedUrl(original, desiredWidth(img));
    if (!srcset || !src) return;

    img.srcset = srcset;
    img.src = src;
    img.addEventListener(
      "error",
      () => {
        if (img.src !== original) {
          img.removeAttribute("srcset");
          img.src = original;
        }
      },
      { once: true }
    );
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
