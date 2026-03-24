(() => {
  const body = document.body;
  if (!body) return;
  const METRIKA_ID = 108214677;

  function initMetrika() {
    window.ym =
      window.ym ||
      function metrikaShim(...args) {
        (window.ym.a = window.ym.a || []).push(args);
      };
    window.ym.l = window.ym.l || Date.now();

    if (!document.querySelector(`script[src*="mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}"]`)) {
      const script = document.createElement("script");
      script.async = true;
      script.src = `https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}`;
      document.head.appendChild(script);
    }

    window.ym(METRIKA_ID, "init", {
      clickmap: true,
      trackLinks: true,
      accurateTrackBounce: true,
      webvisor: true,
    });
  }

  function trackAnalytics(goal, params = {}) {
    try {
      if (typeof window.ym === "function") {
        window.ym(METRIKA_ID, "reachGoal", goal, params);
      }

      if (typeof window.gtag === "function") {
        window.gtag("event", goal, params);
      }
    } catch (error) {
      console.warn("Analytics tracking failed", goal, error);
    }
  }

  initMetrika();

  const SUPABASE_CONFIG = window.__ABHAZBEREG_SUPABASE_CONFIG__ || {
    url: "https://chnyazvybzzryduhgopa.supabase.co",
    anonKey: "sb_publishable_O-ymNKudqlqBER490d90-Q_uYm8XrUc",
  };
  const SUPABASE_MODULE_URL = "https://esm.sh/@supabase/supabase-js@2";
  const FILTER_GROUPS = ["distance", "food", "price", "city", "beach", "room", "stay"];
  let supabaseClientPromise = null;

  const lightbox = document.createElement("div");
  lightbox.className = "lightbox";
  lightbox.setAttribute("hidden", "");
  lightbox.innerHTML = `
    <button class="lightbox__close" type="button" aria-label="Закрыть">×</button>
    <img class="lightbox__image" alt="" />
  `;
  body.appendChild(lightbox);

  const lightboxImage = lightbox.querySelector(".lightbox__image");
  const closeButton = lightbox.querySelector(".lightbox__close");

  const openLightbox = (src, alt) => {
    if (!src || !lightboxImage) return;
    lightboxImage.src = src;
    lightboxImage.alt = alt || "";
    lightbox.removeAttribute("hidden");
    body.classList.add("modal-open");
  };

  const closeLightbox = () => {
    lightbox.setAttribute("hidden", "");
    body.classList.remove("modal-open");
    if (lightboxImage) {
      lightboxImage.src = "";
      lightboxImage.alt = "";
    }
  };

  function isSupabaseConfigured() {
    return Boolean(SUPABASE_CONFIG.url && SUPABASE_CONFIG.anonKey);
  }

  async function getSupabaseClient() {
    if (!isSupabaseConfigured()) return null;
    if (!supabaseClientPromise) {
      supabaseClientPromise = import(SUPABASE_MODULE_URL).then(({ createClient }) =>
        createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey)
      );
    }
    return supabaseClientPromise;
  }

  async function fetchListings(options = {}) {
    const client = await getSupabaseClient();
    if (!client) return [];

    let query = client
      .from("listings")
      .select(
        "id, slug, source_kind, title, summary, excerpt, city, page_url, telegram_url, published_at, has_video, cover_url, details, listing_media(id, media_role, sort_order, public_url, storage_path, mime_type, source_url, details)"
      )
      .eq("is_active", true)
      .order("published_at", { ascending: false, nullsFirst: false })
      .order("id", { ascending: false });

    if (options.sourceKind) query = query.eq("source_kind", options.sourceKind);
    if (options.slug) query = query.eq("slug", options.slug).limit(1);

    const { data, error } = await query;
    if (error) throw error;
    return data || [];
  }

  async function fetchListingBySlug(slug) {
    const rows = await fetchListings({ slug });
    return rows[0] || null;
  }

  function localCardFallback(row) {
    if (!row?.slug) return "";
    const folder = row.source_kind === "kvartira" ? "cards" : "cards";
    return `/media/${folder}/${row.slug}.jpg`;
  }

  function normalizeMediaUrl(value) {
    if (!value || typeof value !== "string") return "";
    const raw = value.trim();
    if (!raw) return "";

    if (raw.includes("/storage/v1/object/public/site-media/http")) {
      const marker = "/storage/v1/object/public/site-media/";
      const idx = raw.indexOf(marker);
      const nested = raw.slice(idx + marker.length);
      try {
        const decoded = decodeURIComponent(nested);
        if (decoded.startsWith("http://") || decoded.startsWith("https://")) {
          return decoded;
        }
      } catch (error) {
        console.warn("Не удалось декодировать вложенный URL медиа", raw, error);
      }
    }

    return raw;
  }

  function pickCoverUrl(row) {
    const media = Array.isArray(row.listing_media) ? [...row.listing_media] : [];
    media.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    const card = media.find((item) => item.media_role === "card" && normalizeMediaUrl(item.public_url));
    const image = media.find((item) => normalizeMediaUrl(item.public_url) && (item.mime_type || "").startsWith("image/"));
    return (
      normalizeMediaUrl(card?.public_url) ||
      normalizeMediaUrl(image?.public_url) ||
      normalizeMediaUrl(row.cover_url) ||
      localCardFallback(row)
    );
  }

  function attachImageFallback(image, row) {
    if (!image) return;
    image.addEventListener(
      "error",
      () => {
        const fallback = localCardFallback(row);
        if (fallback && image.src !== new URL(fallback, window.location.origin).href) {
          image.src = fallback;
          return;
        }
        image.removeAttribute("src");
      },
      { once: true }
    );
  }

  function textValue(value) {
    if (Array.isArray(value)) return value.filter(Boolean).join("|");
    if (typeof value === "string") return value.trim();
    if (typeof value === "number") return String(value);
    return "";
  }

  function pathnameFromUrl(url, fallback) {
    if (!url) return fallback;
    try {
      return new URL(url, window.location.origin).pathname;
    } catch (error) {
      return fallback;
    }
  }

  function createTextNode(tag, text) {
    const node = document.createElement(tag);
    node.textContent = text || "";
    return node;
  }

  function applyFilterData(card, filters) {
    const safeFilters = filters || {};
    card.dataset.filterDistance = textValue(safeFilters.distance);
    card.dataset.filterFood = textValue(safeFilters.food);
    card.dataset.filterPrice = textValue(safeFilters.price);
    card.dataset.filterCity = textValue(safeFilters.city);
    card.dataset.filterBeach = textValue(safeFilters.beach);
    card.dataset.filterRoom = textValue(safeFilters.room);
    card.dataset.filterStay = textValue(safeFilters.stay);
  }

  function renderHotelCards(rows, grid) {
    const fragment = document.createDocumentFragment();

    rows.forEach((row) => {
      const card = document.createElement("a");
      card.className = "catalog-card";
      card.href = pathnameFromUrl(row.page_url, `/hotels/${row.slug}/`);
      applyFilterData(card, row.details?.filters);

      const image = document.createElement("img");
      image.loading = "lazy";
      image.alt = row.title || "";
      image.src = pickCoverUrl(row);
      attachImageFallback(image, row);
      card.appendChild(image);

      card.appendChild(createTextNode("h3", row.title || ""));
      card.appendChild(createTextNode("p", row.summary || row.excerpt || ""));
      fragment.appendChild(card);
    });

    grid.replaceChildren(fragment);
  }

  function renderKvartiraCards(rows, grid) {
    const fragment = document.createDocumentFragment();

    rows.forEach((row) => {
      const card = document.createElement("a");
      card.className = "catalog-card";
      card.href = row.telegram_url || row.page_url || "/kvartira/";
      card.target = "_blank";
      card.rel = "noopener noreferrer";

      const mediaWrap = document.createElement("div");
      mediaWrap.className = "catalog-card__media-wrap";

      if (row.has_video) {
        const badge = document.createElement("span");
        badge.className = "catalog-card__badge";
        badge.textContent = "Видео";
        mediaWrap.appendChild(badge);
      }

      const image = document.createElement("img");
      image.loading = "lazy";
      image.alt = row.title || "";
      image.src = pickCoverUrl(row);
      attachImageFallback(image, row);
      mediaWrap.appendChild(image);

      card.appendChild(mediaWrap);
      card.appendChild(createTextNode("h3", row.title || ""));
      card.appendChild(createTextNode("p", row.summary || row.excerpt || row.details?.excerpt || ""));
      fragment.appendChild(card);
    });

    grid.replaceChildren(fragment);
  }

  function formatLeadText(row) {
    const lead = row?.details?.lead || row?.summary || row?.excerpt || "";
    return lead
      .replace(/\s*🏖\s*/g, "\n🏖 ")
      .replace(/\s*👥\s*/g, "\n👥 ")
      .trim();
  }

  function formatPublishedDate(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return {
      machine: value,
      human: new Intl.DateTimeFormat("ru-RU", {
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(date),
    };
  }

  function replaceWithLines(element, text) {
    const lines = String(text || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) return;

    const fragment = document.createDocumentFragment();
    lines.forEach((line, index) => {
      if (index > 0) fragment.appendChild(document.createElement("br"));
      fragment.appendChild(document.createTextNode(line));
    });
    element.replaceChildren(fragment);
  }

  function resolveSupabaseMediaUrl(item, row) {
    if (item && item.public_url) return item.public_url;
    const raw = (item && item.storage_path) || (item && item.source_url) || '';
    if (!raw) return '';
    if (/^https?:\/\//i.test(raw)) {
      const marker = `/storage/v1/object/public/${SUPABASE_CONFIG.storageBucket}/`;
      const idx = raw.indexOf(marker);
      if (idx !== -1) {
        let rel = decodeURIComponent(raw.slice(idx + marker.length));
        while (/^https?:\/\//i.test(rel)) {
          const nextIdx = rel.indexOf(marker);
          if (nextIdx === -1) break;
          rel = decodeURIComponent(rel.slice(nextIdx + marker.length));
        }
        return `${SUPABASE_CONFIG.url}/storage/v1/object/public/${SUPABASE_CONFIG.storageBucket}/${rel.split('/').map(encodeURIComponent).join('/')}`;
      }
      return raw;
    }
    const rel = raw.replace(/^\/+/, '');
    return `${SUPABASE_CONFIG.url}/storage/v1/object/public/${SUPABASE_CONFIG.storageBucket}/${rel.split('/').map(encodeURIComponent).join('/')}`;
  }

  function renderHotelMedia(row, grid) {
    const fragment = document.createDocumentFragment();
    const media = Array.isArray(row.listing_media) ? [...row.listing_media] : [];
    media
      .filter((item) => item.media_role !== "card" && (item.public_url || item.storage_path || item.source_url || item.mime_type === "application/x-telegram-embed" || (item.details && item.details.telegram_post)))
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .forEach((item, index) => {
        if ((item.mime_type || "").startsWith("video/")) {
          const resolvedUrl = resolveSupabaseMediaUrl(item, row);
          if (!resolvedUrl) return;
          const video = document.createElement("video");
          video.className = "local-video";
          video.controls = true;
          video.preload = "metadata";
          video.playsInline = true;
          video.src = resolvedUrl;
          fragment.appendChild(video);
          return;
        }

        if ((item.details && item.details.telegram_post) || item.mime_type === "application/x-telegram-embed") {
          const wrap = document.createElement("div");
          wrap.className = "video-embed video-embed--telegram";

          const script = document.createElement("script");
          script.async = true;
          script.src = "https://telegram.org/js/telegram-widget.js?22";
          script.dataset.telegramPost = item.details?.telegram_post || "";
          script.dataset.width = "100%";
          script.dataset.userpic = "false";
          script.dataset.single = "1";
          wrap.appendChild(script);

          if (item.source_url) {
            const link = document.createElement("a");
            link.className = "video-link";
            link.href = item.source_url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "Открыть видео в Telegram";
            wrap.appendChild(link);
          }

          fragment.appendChild(wrap);
          return;
        }

        const resolvedUrl = resolveSupabaseMediaUrl(item, row);
        if (!resolvedUrl) return;
        const image = document.createElement("img");
        image.loading = "lazy";
        image.src = resolvedUrl;
        image.alt = `${row.title || "Объект"} фото ${index + 1}`;
        image.classList.add("media-grid__zoomable");
        fragment.appendChild(image);
      });

    if (fragment.childNodes.length > 0) {
      grid.replaceChildren(fragment);
    }
  }

  function initFilters() {
    const grid = document.getElementById("catalog-grid");
    if (!grid) return { refresh: () => {} };

    const chips = Array.from(document.querySelectorAll(".filter-chip"));
    const visibleCount = document.getElementById("visible-count");
    const emptyNote = document.getElementById("filter-empty");
    const clearBtn = document.getElementById("clear-filters");
    const openFiltersBtn = document.getElementById("open-filters");
    const filtersModal = document.getElementById("filters-modal");
    const closeFilterEls = Array.from(document.querySelectorAll("[data-close-filters]"));
    const selected = Object.fromEntries(FILTER_GROUPS.map((group) => [group, new Set()]));

    function getCards() {
      return Array.from(grid.querySelectorAll(".catalog-card"));
    }

    function parseValues(card, group) {
      const key = `filter${group.charAt(0).toUpperCase()}${group.slice(1)}`;
      const raw = card.dataset[key] || "";
      return raw.split("|").map((value) => value.trim()).filter(Boolean);
    }

    function applyFilters() {
      let shown = 0;
      getCards().forEach((card) => {
        let ok = true;
        for (const group of FILTER_GROUPS) {
          if (selected[group].size === 0) continue;
          const values = parseValues(card, group);
          const hit = values.some((value) => selected[group].has(value));
          if (!hit) {
            ok = false;
            break;
          }
        }
        card.hidden = !ok;
        if (ok) shown += 1;
      });

      if (visibleCount) visibleCount.textContent = String(shown);
      if (emptyNote) emptyNote.hidden = shown !== 0;
    }

    chips.forEach((chip) => {
      chip.type = "button";
      chip.setAttribute("aria-pressed", "false");
      chip.addEventListener("click", () => {
        const group = chip.dataset.group;
        const value = chip.dataset.value;
        if (!group || !value || !selected[group]) return;

        if (selected[group].has(value)) {
          selected[group].delete(value);
          chip.classList.remove("is-active");
          chip.setAttribute("aria-pressed", "false");
        } else {
          selected[group].add(value);
          chip.classList.add("is-active");
          chip.setAttribute("aria-pressed", "true");
        }
        applyFilters();
      });
    });

    clearBtn?.addEventListener("click", () => {
      FILTER_GROUPS.forEach((group) => selected[group].clear());
      chips.forEach((chip) => {
        chip.classList.remove("is-active");
        chip.setAttribute("aria-pressed", "false");
      });
      applyFilters();
    });

    openFiltersBtn?.addEventListener("click", () => {
      if (!filtersModal) return;
      filtersModal.hidden = false;
      body.classList.add("modal-open");
      trackAnalytics("open_filters");
    });

    closeFilterEls.forEach((element) => {
      element.addEventListener("click", () => {
        if (!filtersModal) return;
        filtersModal.hidden = true;
        body.classList.remove("modal-open");
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && filtersModal && !filtersModal.hidden) {
        filtersModal.hidden = true;
        body.classList.remove("modal-open");
      }
    });

    applyFilters();
    return { refresh: applyFilters };
  }

  async function hydrateHomeCatalog(filtersController) {
    const grid = document.getElementById("catalog-grid");
    if (!grid) return;

    try {
      const rows = await fetchListings({ sourceKind: "hotel" });
      if (!rows.length) return;
      renderHotelCards(rows, grid);
      filtersController.refresh();
    } catch (error) {
      console.error("Не удалось загрузить каталог отелей из Supabase", error);
      filtersController.refresh();
    }
  }

  async function hydrateKvartiraCatalog() {
    const grid = document.getElementById("kvartira-catalog-grid");
    if (!grid) return;

    try {
      const rows = await fetchListings({ sourceKind: "kvartira" });
      if (!rows.length) return;
      renderKvartiraCards(rows, grid);
    } catch (error) {
      console.error("Не удалось загрузить каталог квартир из Supabase", error);
    }
  }

  async function hydrateHotelPage() {
    const hotelRoot = document.querySelector(".hotel-page-v2");
    if (!hotelRoot) return;

    const match = window.location.pathname.match(/^\/hotels\/([^/]+)\/?$/);
    if (!match) return;

    try {
      const row = await fetchListingBySlug(match[1]);
      if (!row) return;

      const heroTitle = document.querySelector(".hotel-hero-v2 h1");
      const heroLead = document.querySelector(".hotel-hero-v2 .lead");
      const updatedTime = document.querySelector(".hotel-hero-v2 .updated time");
      const mediaGrid = document.querySelector(".hotel-media-section .media-grid");
      const mediaLink = document.querySelector(".hotel-media-section .media-note a");

      if (heroTitle && row.title) heroTitle.textContent = row.title;
      if (heroLead) {
        const lead = formatLeadText(row);
        if (lead) replaceWithLines(heroLead, lead);
      }

      const published = formatPublishedDate(row.published_at);
      if (updatedTime && published) {
        updatedTime.dateTime = published.machine;
        updatedTime.textContent = published.human;
      }

      if (mediaGrid) renderHotelMedia(row, mediaGrid);
      if (mediaLink && row.telegram_url) {
        mediaLink.href = row.telegram_url;
        mediaLink.textContent = row.telegram_url.replace("https://t.me/", "@");
      }

      if (row.title) {
        const baseTitle = document.title.includes("—")
          ? document.title.split("—").slice(1).join("—").trim()
          : "обзор, фото, видео и цены";
        document.title = `${row.title} — ${baseTitle}`;
      }
    } catch (error) {
      console.error("Не удалось обновить страницу объекта из Supabase", error);
    }
  }

  closeButton?.addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) closeLightbox();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !lightbox.hasAttribute("hidden")) closeLightbox();
  });

  document.addEventListener("click", (event) => {
    const image = event.target.closest(".media-grid img, .hotel-media-section img");
    if (!image) return;

    if (image.classList.contains("local-video-preview")) {
      const block = image.closest(".video-embed");
      const link = block?.querySelector(".video-link");
      if (link?.href) window.open(link.href, "_blank", "noopener,noreferrer");
      return;
    }

    image.classList.add("media-grid__zoomable");
    openLightbox(image.currentSrc || image.src, image.alt);
  });

  document.addEventListener("click", (event) => {
    const video = event.target.closest(".local-video");
    if (!video) return;
    if (video.paused) video.play();
    else video.pause();
  });

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link) return;

    const href = (link.getAttribute("href") || "").toLowerCase();
    if (!href) return;

    if (href.includes("wa.me") || href.includes("whatsapp")) {
      trackAnalytics("click_whatsapp", { href });
      return;
    }

    if (href.includes("t.me") || href.includes("telegram")) {
      trackAnalytics("click_telegram", { href });
      return;
    }

    if (link.classList.contains("catalog-card")) {
      trackAnalytics("open_hotel_card", { href });
    }
  });

  const filtersController = initFilters();
  hydrateHomeCatalog(filtersController);
  hydrateKvartiraCatalog();
  hydrateHotelPage();
})();
