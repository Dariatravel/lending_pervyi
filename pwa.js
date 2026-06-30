(() => {
  const DISMISS_KEY = "abhazbereg-pwa-install-dismissed";
  const isStandalone =
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
    window.navigator.standalone === true;

  function initHomeTopStartup() {
    const path = window.location.pathname || "/";
    const isHomePage = path === "/" || path === "/index.html";
    if (!isHomePage || window.location.hash) return;

    try {
      if ("scrollRestoration" in window.history) {
        window.history.scrollRestoration = "manual";
      }
      sessionStorage.removeItem("abhaz:selectionScroll");
    } catch (error) {
      /* Ignore browser storage/history restrictions. */
    }

    const scrollToTop = () => {
      if (window.location.hash) return;
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    };
    scrollToTop();
    window.addEventListener("load", () => window.requestAnimationFrame(scrollToTop), { once: true });
    window.addEventListener("pageshow", () => window.requestAnimationFrame(scrollToTop), { once: true });
  }

  if ("serviceWorker" in navigator && window.location.protocol !== "file:") {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch((error) => {
        console.warn("PWA registration failed", error);
      });
    });
  }

  function getDismissedState() {
    try {
      return localStorage.getItem(DISMISS_KEY) === "1";
    } catch (error) {
      return false;
    }
  }

  function setDismissedState() {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch (error) {
      /* Ignore storage restrictions in private browsing modes. */
    }
  }

  function initMobileFilterShortcut() {
    const shortcut = document.querySelector("[data-mobile-open-filters]");
    if (!shortcut) return;

    shortcut.addEventListener("click", () => {
      const opener = document.getElementById("open-filters");
      if (opener) {
        opener.click();
        return;
      }
      window.location.hash = "catalog";
    });
  }

  function initPwaInstallCard() {
    const card = document.querySelector("[data-pwa-install-card]");
    if (!card || isStandalone || getDismissedState()) return;

    const installButton = card.querySelector("[data-pwa-install-button]");
    const dismissButton = card.querySelector("[data-pwa-install-dismiss]");
    const textNode = card.querySelector("[data-pwa-install-text]");
    let deferredPrompt = null;

    function showCard() {
      card.hidden = false;
    }

    function hideCard() {
      card.hidden = true;
    }

    dismissButton?.addEventListener("click", () => {
      setDismissedState();
      hideCard();
    });

    installButton?.addEventListener("click", async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      await deferredPrompt.userChoice.catch(() => undefined);
      deferredPrompt = null;
      setDismissedState();
      hideCard();
    });

    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      deferredPrompt = event;
      if (installButton) installButton.hidden = false;
      if (textNode) {
        textNode.textContent = "Установите сайт как приложение: каталог, карта и контакты откроются быстрее.";
      }
      showCard();
    });

    const isSmallScreen = window.matchMedia?.("(max-width: 760px)")?.matches;
    const isiOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent || "");
    if (isSmallScreen || isiOS) showCard();
  }

  initHomeTopStartup();
  initMobileFilterShortcut();
  initPwaInstallCard();
})();
