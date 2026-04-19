(() => {
  const body = document.body;
  if (!body) return;
  const METRIKA_ID = 108214677;
  const GA4_ID = "G-MZ2NTRDDJ5";

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

  function initGA4() {
    window.dataLayer = window.dataLayer || [];
    window.gtag =
      window.gtag ||
      function gtagShim() {
        window.dataLayer.push(arguments);
      };

    if (!document.querySelector(`script[src*="googletagmanager.com/gtag/js?id=${GA4_ID}"]`)) {
      const script = document.createElement("script");
      script.async = true;
      script.src = `https://www.googletagmanager.com/gtag/js?id=${GA4_ID}`;
      document.head.appendChild(script);
    }

    window.gtag("js", new Date());
    window.gtag("config", GA4_ID);
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
  initGA4();

  const SUPABASE_CONFIG = window.__ABHAZBEREG_SUPABASE_CONFIG__ || {
    url: "https://chnyazvybzzryduhgopa.supabase.co",
    anonKey: "sb_publishable_O-ymNKudqlqBER490d90-Q_uYm8XrUc",
    storageBucket: "site-media",
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
    const folder = row.source_kind === "kvartira" ? "kvartira-cards" : "cards";
    return `/media/${folder}/${row.slug}.jpg`;
  }

  /** Turn /media/... paths into public Supabase Storage URLs (covers cards, hotel galleries, videos — not in static repo). */
  function absolutizeKvartiraCoverUrl(url) {
    const n = normalizeMediaUrl(url);
    if (!n) return "";
    if (n.startsWith("http://") || n.startsWith("https://")) return n;
    if (n.startsWith("/media/")) return n;
    return n;
  }

  /** Локальные медиа уже лежат на сайте, поэтому только инициируем перезагрузку video после гидрации. */
  function absolutizeHotelSiteConceptMedia() {
    const roots = [
      document.querySelector(".hotel-site-concept"),
      document.querySelector(".site-concept"),
    ].filter(Boolean);

    roots.forEach((root) => {
      root.querySelectorAll("video").forEach((video) => {
        const hasSrc = Boolean(video.getAttribute("src"));
        const hasSourceChild = Boolean(video.querySelector("source[src]"));
        if (!hasSrc && !hasSourceChild) return;
        try {
          video.load();
        } catch (error) {
          /* ignore */
        }
      });
    });
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

  /**
   * Kvartira covers in Storage often use `slug-cover.jpg`, sometimes `slug.jpg` only.
   * DB may point at a missing variant — try both after media/cover_url.
   */
  function kvartiraCoverCandidates(row) {
    const media = Array.isArray(row.listing_media) ? [...row.listing_media] : [];
    media.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    const card = media.find((item) => item.media_role === "card" && normalizeMediaUrl(item.public_url));
    const image = media.find((item) => normalizeMediaUrl(item.public_url) && (item.mime_type || "").startsWith("image/"));
    const urls = [];
    const push = (u) => {
      const n = normalizeMediaUrl(u);
      if (!n) return;
      const abs = absolutizeKvartiraCoverUrl(n);
      if (abs && !urls.includes(abs)) urls.push(abs);
    };
    push(card?.public_url);
    push(image?.public_url);
    push(row.cover_url);
    if (row.slug) {
      push(`/media/kvartira-cards/${row.slug}-cover.jpg`);
      push(`/media/kvartira-cards/${row.slug}.jpg`);
    }
    return urls;
  }

  function pickCoverUrl(row) {
    if (row.source_kind === "kvartira") {
      const urls = kvartiraCoverCandidates(row);
      return urls[0] || "";
    }

    const media = Array.isArray(row.listing_media) ? [...row.listing_media] : [];
    media.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    const card = media.find((item) => item.media_role === "card" && normalizeMediaUrl(item.public_url));
    const image = media.find((item) => normalizeMediaUrl(item.public_url) && (item.mime_type || "").startsWith("image/"));
    const raw =
      normalizeMediaUrl(card?.public_url) ||
      normalizeMediaUrl(image?.public_url) ||
      normalizeMediaUrl(row.cover_url) ||
      localCardFallback(row);
    return raw || localCardFallback(row);
  }

  function attachImageFallback(image, row) {
    if (!image) return;

    if (row.source_kind === "kvartira") {
      const candidates = kvartiraCoverCandidates(row);
      if (candidates.length < 2) {
        image.addEventListener(
          "error",
          () => {
            image.removeAttribute("src");
          },
          { once: true }
        );
        return;
      }
      let attempt = 0;
      image.addEventListener("error", function tryKvartiraCover() {
        attempt += 1;
        if (attempt < candidates.length) {
          image.src = candidates[attempt];
        } else {
          image.removeAttribute("src");
          image.removeEventListener("error", tryKvartiraCover);
        }
      });
      return;
    }

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

  const CITY_LABELS = {
    sukhum: "Сухум",
    "new-afon": "Новый Афон",
    gudauta: "Гудаута",
    ldzaa: "Лдзаа",
    pitsunda: "Пицунда",
    alakhadzy: "Алахадзы",
    gagra: "Гагра",
    tsandripsh: "Цандрипш",
  };

  const DISTANCE_BY_FILTER = {
    beachfront: "0 минут до пляжа",
    "up-to-5": "до 5 минут до пляжа",
    "up-to-10": "до 10 минут до пляжа",
    "over-10": "более 10 минут до пляжа",
  };

  function firstValue(value) {
    if (Array.isArray(value)) return String(value[0] || "").trim();
    return String(value || "").split("|")[0].trim();
  }

  function extractCityFromSummary(text) {
    const cleaned = String(text || "").replace(/🏖|👥|📍/g, "").trim();
    const match = cleaned.match(/^([А-Яа-яЁёA-Za-z\- ]+?)(?:[.,]|$)/);
    return match ? match[1].trim() : "";
  }

  function extractDistanceFromSummary(text) {
    const cleaned = String(text || "").replace(/\s+/g, " ").trim();
    let match = cleaned.match(
      /(\d+\s*(?:-|–)?\s*\d*\s*мин(?:ут[аы]?|\.?)\s*(?:пешком\s*)?(?:до\s*)?пляжа)/i
    );
    if (match) return match[1].replace(/\s+/g, " ").trim();
    match = cleaned.match(/пляжа\s+в\s+(\d+\s*(?:-|–)?\s*\d*\s*мин(?:ут[аы]?|\.?)(?:\s*пешком)?)/i);
    if (match) return `${match[1].replace(/\s+/g, " ").trim()} до пляжа`;
    match = cleaned.match(/(\d+\s*(?:-|–)?\s*\d*\s*мин(?:ут[аы]?|\.?))\s+пешком\s+до\s+пляжа/i);
    if (match) return `${match[1].replace(/\s+/g, " ").trim()} до пляжа`;
    match = cleaned.match(/до\s+пляжа\s+(\d+\s*(?:-|–)?\s*\d*\s*мин(?:ут[аы]?|\.?))/i);
    if (match) return `${match[1].replace(/\s+/g, " ").trim()} до пляжа`;
    return "";
  }

  function extractCapacityFromSummary(text) {
    const cleaned = String(text || "").replace(/\s+/g, " ").trim();
    const placement = cleaned.match(/(размещ(?:ение|ается|ение от)?[^.,;!]*чел(?:овек)?[^.,;!]*)/i);
    if (placement) return placement[1].trim();
    const capacity = cleaned.match(/(вместимост[^\.,;!]*чел(?:овек)?[^.,;!]*)/i);
    return capacity ? capacity[1].trim() : "";
  }

  function formatHotelCardSummary(row) {
    const source = row?.summary || row?.excerpt || row?.details?.lead || "";
    const filters = row?.details?.filters || {};
    const city = extractCityFromSummary(source) || CITY_LABELS[firstValue(filters.city)] || "Абхазия";
    const distance = extractDistanceFromSummary(source) || DISTANCE_BY_FILTER[firstValue(filters.distance)] || "до пляжа";
    const capacity = extractCapacityFromSummary(source) || "размещение уточняйте";
    return `${city}. ${distance}, ${capacity}.`;
  }

  /** Короткие строки 📍 / 🏖 как у карточек отелей на главной (не абзацы из excerpt). */
  function extractKvartiraPinLine(text) {
    const t = String(text || "").trim();
    if (!t.includes("📍")) return "";
    const idx = t.indexOf("📍");
    let slice = t.slice(idx);
    const beachIdx = slice.search(/🏖|🏝/);
    if (beachIdx !== -1) slice = slice.slice(0, beachIdx).trim();
    slice = slice.replace(/\s+/g, " ").trim();
    if (slice.length > 130) slice = `${slice.slice(0, 127).trim()}…`;
    return slice;
  }

  function extractKvartiraBeachLine(text, filters) {
    const t = String(text || "").trim();
    const idx = t.search(/🏖|🏝/);
    if (idx !== -1) {
      let slice = t.slice(idx);
      slice = slice.split(/\s*✔️/)[0].trim();
      slice = slice.replace(/\s+/g, " ");
      if (slice.length > 130) slice = `${slice.slice(0, 127).trim()}…`;
      return slice;
    }
    const dist =
      extractDistanceFromSummary(t) || DISTANCE_BY_FILTER[firstValue(filters?.distance || {})] || "";
    if (dist) return `🏖 ${dist}`;
    return "";
  }

  function clampKvartiraCardDescription(text) {
    let t = String(text || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    t = t.replace(/^✔️[^:]*:\s*/i, "");
    const sentence = t.match(/^(.{12,118}?[.!?])(\s|$)/);
    if (sentence) return sentence[1].trim();
    if (t.length <= 118) return t;
    const cut = t.slice(0, 115);
    const sp = cut.lastIndexOf(" ");
    return `${sp > 35 ? cut.slice(0, sp) : cut}…`;
  }

  function formatKvartiraCardSummary(row) {
    const source = row?.summary || row?.excerpt || row?.details?.lead || "";
    const filters = row?.details?.filters || {};
    let line1 = extractKvartiraPinLine(source);
    if (!line1) {
      const fromFilter = CITY_LABELS[firstValue(filters.city)];
      const fromLead = source.length < 120 ? extractCityFromSummary(source) : "";
      const city = fromFilter || fromLead;
      if (city) line1 = `📍${city}.`;
    }
    const line2 = extractKvartiraBeachLine(source, filters);
    if (line1 && line2) return `${line1}\n${line2}`;
    if (line1) return line1;
    if (line2) return line2;
    return clampKvartiraCardDescription(source);
  }

  function renderHotelCards(rows, grid) {
    const fragment = document.createDocumentFragment();

    rows.forEach((row) => {
      const card = document.createElement("a");
      card.className = "catalog-card";
      card.href = pathnameFromUrl(row.page_url, `/hotels/${row.slug}/`);
      applyFilterData(card, row.details?.filters);

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
      card.appendChild(createTextNode("p", formatHotelCardSummary(row)));
      fragment.appendChild(card);
    });

    grid.replaceChildren(fragment);
  }

  function renderKvartiraCards(rows, grid) {
    const fragment = document.createDocumentFragment();

    rows.forEach((row) => {
      const card = document.createElement("a");
      card.className = "catalog-card";
      card.href = pathnameFromUrl(row.page_url, row.telegram_url || "/kvartira/");

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
      const desc = document.createElement("p");
      replaceWithLines(desc, formatKvartiraCardSummary(row));
      card.appendChild(desc);
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
    if (item && typeof item.source_url === "string" && item.source_url.startsWith("/media/")) {
      return item.source_url;
    }
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

  function cardCatalogCategoryText(card) {
    const h3 = card.querySelector("h3");
    const img = card.querySelector("img");
    return `${h3?.textContent || ""} ${img?.getAttribute("alt") || ""}`.toLowerCase();
  }

  /** Rough title-based match for category tiles (main catalog is hotels/guest houses/cabins). */
  function matchesCatalogCategory(slug, text) {
    if (!slug) return true;
    if (slug === "cabin") {
      return /домик|коттедж|глепинг|bungalo|шале|глэмпинг|glemping|бунгало|шалэ/.test(text);
    }
    if (slug === "guesthouse") {
      return /гостев|пансион/.test(text);
    }
    if (slug === "hotel") {
      return /отель|гостиница|инн|inn|апарт[\s-]*отел/.test(text);
    }
    return true;
  }

  function initFilters() {
    const grid = document.getElementById("catalog-grid");
    if (!grid) {
      return {
        refresh: () => {},
        setCatalogCategory: () => {},
        setGroupValues: () => {},
        clearGroups: () => {},
      };
    }

    const chips = Array.from(document.querySelectorAll(".filter-chip"));
    const visibleCount = document.getElementById("visible-count");
    const emptyNote = document.getElementById("filter-empty");
    const clearBtn = document.getElementById("clear-filters");
    const openFiltersBtn = document.getElementById("open-filters");
    const filtersModal = document.getElementById("filters-modal");
    const closeFilterEls = Array.from(document.querySelectorAll("[data-close-filters]"));
    const selected = Object.fromEntries(FILTER_GROUPS.map((group) => [group, new Set()]));
    let catalogCategorySlug = null;

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
        if (ok && catalogCategorySlug && !matchesCatalogCategory(catalogCategorySlug, cardCatalogCategoryText(card))) {
          ok = false;
        }
        card.hidden = !ok;
        if (ok) shown += 1;
      });

      if (visibleCount) visibleCount.textContent = String(shown);
      if (emptyNote) emptyNote.hidden = shown !== 0;
    }

    function setCatalogCategory(slug) {
      catalogCategorySlug = slug && String(slug).trim() ? String(slug).trim() : null;
      applyFilters();
    }

    function syncChipState() {
      chips.forEach((chip) => {
        const group = chip.dataset.group;
        const value = chip.dataset.value;
        const active = Boolean(group && value && selected[group] && selected[group].has(value));
        chip.classList.toggle("is-active", active);
        chip.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function setGroupValues(group, values) {
      if (!selected[group]) return;
      selected[group].clear();
      (values || []).forEach((value) => {
        const cleaned = String(value || "").trim();
        if (cleaned) selected[group].add(cleaned);
      });
      syncChipState();
      applyFilters();
    }

    function clearGroups(groups) {
      (groups || FILTER_GROUPS).forEach((group) => {
        if (selected[group]) selected[group].clear();
      });
      syncChipState();
      applyFilters();
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
        } else {
          selected[group].add(value);
        }
        syncChipState();
        applyFilters();
      });
    });

    clearBtn?.addEventListener("click", () => {
      FILTER_GROUPS.forEach((group) => selected[group].clear());
      syncChipState();
      catalogCategorySlug = null;
      applyFilters();
    });

    const openFiltersModal = () => {
      if (!filtersModal) return;
      filtersModal.hidden = false;
      // Start enter transition on the next frame so CSS transform animates correctly.
      requestAnimationFrame(() => filtersModal.classList.add("is-visible"));
      body.classList.add("modal-open");
      trackAnalytics("open_filters");
    };

    const closeFiltersModal = () => {
      if (!filtersModal) return;
      filtersModal.classList.remove("is-visible");
      body.classList.remove("modal-open");
      window.setTimeout(() => {
        if (!filtersModal.classList.contains("is-visible")) {
          filtersModal.hidden = true;
        }
      }, 360);
    };

    openFiltersBtn?.addEventListener("click", openFiltersModal);

    closeFilterEls.forEach((element) => {
      element.addEventListener("click", () => {
        closeFiltersModal();
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && filtersModal && !filtersModal.hidden) {
        closeFiltersModal();
      }
    });

    syncChipState();
    applyFilters();
    return { refresh: applyFilters, setCatalogCategory, setGroupValues, clearGroups };
  }

  function initSearchBar(filtersController) {
    const form = document.getElementById("home-search-form");
    if (!form || !filtersController) return;

    const citySelect = document.getElementById("search-city");
    const distanceSelect = document.getElementById("search-distance");
    const beachSelect = document.getElementById("search-beach");
    const priceSelect = document.getElementById("search-price");
    const guestsInput = document.getElementById("search-guests");
    const checkinInput = document.getElementById("search-checkin");
    const checkoutInput = document.getElementById("search-checkout");

    if (citySelect) {
      const cities = Array.from(document.querySelectorAll('.filter-chip[data-group="city"]'));
      const existing = new Set(Array.from(citySelect.options).map((o) => o.value));
      cities.forEach((chip) => {
        const value = chip.dataset.value || "";
        if (!value || existing.has(value)) return;
        const option = document.createElement("option");
        option.value = value;
        option.textContent = chip.textContent?.trim() || value;
        citySelect.appendChild(option);
        existing.add(value);
      });
    }

    const today = new Date();
    const plusWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
    const toISODate = (d) => d.toISOString().slice(0, 10);
    if (checkinInput && !checkinInput.value) checkinInput.value = toISODate(today);
    if (checkoutInput && !checkoutInput.value) checkoutInput.value = toISODate(plusWeek);

    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const city = citySelect?.value || "";
      const distance = distanceSelect?.value || "";
      const beach = beachSelect?.value || "";
      const price = priceSelect?.value || "";
      const guests = Number(guestsInput?.value || 0);

      filtersController.setGroupValues("city", city ? [city] : []);
      filtersController.setGroupValues("distance", distance ? [distance] : []);
      filtersController.setGroupValues("beach", beach ? [beach] : []);
      filtersController.setGroupValues("price", price ? [price] : []);

      if (Number.isFinite(guests) && guests >= 5) {
        filtersController.setGroupValues("room", ["five-plus"]);
      } else {
        filtersController.setGroupValues("room", []);
      }

      document.getElementById("catalog")?.scrollIntoView({ behavior: "smooth", block: "start" });
      trackAnalytics("home_search_submit", {
        city,
        distance,
        beach,
        price,
        guests: Number.isFinite(guests) ? guests : null,
      });
    });
  }

  function initHeroVideoQuality() {
    const video = document.querySelector(".site-concept__hero-video-player");
    if (!video) return;

    const inlineSrc = (video.getAttribute("src") || "").trim();
    const rawHigh = video.dataset.highSrc || "";
    const rawLow = video.dataset.lowSrc || "";
    let highSrc = rawHigh ? absolutizeKvartiraCoverUrl(rawHigh) || rawHigh : "";
    let lowSrc = rawLow ? absolutizeKvartiraCoverUrl(rawLow) || rawLow : "";

    // На GitHub Pages файлы под /media/videos/*.mp4 часто — текстовые Git LFS pointer, не MP4.
    const isNonHttpMediaVideoPath = (url) =>
      typeof url === "string" && url.startsWith("/media/videos/");
    if (isNonHttpMediaVideoPath(highSrc) && inlineSrc.startsWith("https://")) {
      highSrc = inlineSrc;
    }
    if (isNonHttpMediaVideoPath(lowSrc) && inlineSrc.startsWith("https://")) {
      lowSrc = inlineSrc.includes("vertical-high")
        ? inlineSrc.replace("vertical-high", "vertical-low")
        : inlineSrc;
    }

    if (!highSrc && !lowSrc) return;

    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const effectiveType = String(connection?.effectiveType || "").toLowerCase();
    const saveDataEnabled = Boolean(connection?.saveData);
    const shouldPreferLow = saveDataEnabled || ["slow-2g", "2g", "3g"].includes(effectiveType);
    const preferredSrc = shouldPreferLow ? lowSrc : highSrc;
    const fallbackSrc = shouldPreferLow ? highSrc : lowSrc;

    const selectedSrc = preferredSrc || fallbackSrc;
    if (!selectedSrc) return;

    const applySrc = (url) => {
      video.src = url;
      video.load();
    };

    if (fallbackSrc && fallbackSrc !== selectedSrc) {
      video.addEventListener("error", () => applySrc(fallbackSrc), { once: true });
    }

    applySrc(selectedSrc);
  }

  function initCategoryPicks(filtersController) {
    document.querySelectorAll("a.site-concept__category-card[data-catalog-category]").forEach((link) => {
      link.addEventListener("click", (event) => {
        const slug = link.dataset.catalogCategory;
        if (!slug || slug === "apartment") return;
        event.preventDefault();
        filtersController.setCatalogCategory(slug);
        document.getElementById("catalog")?.scrollIntoView({ behavior: "smooth", block: "start" });
        trackAnalytics("pick_stay_category", { category: slug });
      });
    });
  }

  async function hydrateHomeCatalog(filtersController) {
    const grid = document.getElementById("catalog-grid");
    if (!grid) return;

    // Главная уже содержит полную сетку карточек из статической сборки (разметка с 📍 / 🏖 и <br>).
    // Повторная отрисовка из Supabase заменяет DOM и даёт «мигание»: сначала верстка из HTML/CSS,
    // затем упрощённые карточки из formatHotelCardSummary. Не перезаписываем готовую сетку.
    if (grid.querySelector(".catalog-card")) {
      filtersController.refresh();
      return;
    }

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

  /** Slugs removed from UI (e.g. Telegram service posts, not real listings). */
  const KVARTIRA_EXCLUDED_SLUGS = new Set(["general-1409", "villa-suhum-959"]);

  async function hydrateKvartiraCatalog() {
    const grid = document.getElementById("kvartira-catalog-grid");
    if (!grid) return;

    try {
      const rows = (await fetchListings({ sourceKind: "kvartira" })).filter(
        (row) => row.slug && !KVARTIRA_EXCLUDED_SLUGS.has(row.slug)
      );
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

  function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function createGuestReviewItem(review) {
    const wrap = document.createElement("div");
    wrap.className = "review-item";
    const head = document.createElement("p");
    head.className = "review-head";
    head.textContent = review.head || "";
    const text = document.createElement("p");
    text.className = "review-text";
    text.textContent = review.text || "";
    wrap.append(head, text);
    return wrap;
  }

  let guestReviewsPromise = null;
  function loadGuestReviewsJson() {
    if (!guestReviewsPromise) {
      guestReviewsPromise = fetch("/data/guest-reviews.json")
        .then((res) => {
          if (!res.ok) throw new Error(`guest-reviews ${res.status}`);
          return res.json();
        })
        .then((data) => (Array.isArray(data) ? data : []));
    }
    return guestReviewsPromise;
  }

  async function initRandomGuestReviews() {
    const nodes = document.querySelectorAll("[data-random-reviews]");
    if (!nodes.length) return;
    let list;
    try {
      list = await loadGuestReviewsJson();
    } catch (error) {
      console.warn("Не удалось загрузить отзывы гостей", error);
      return;
    }
    if (!list.length) return;
    for (const el of nodes) {
      const raw = el.getAttribute("data-review-count") || "4";
      let n = parseInt(raw, 10);
      if (!Number.isFinite(n) || n < 1) n = 4;
      n = Math.min(n, list.length);
      const copy = list.slice();
      shuffleInPlace(copy);
      const picked = copy.slice(0, n);
      el.replaceChildren(...picked.map(createGuestReviewItem));
    }
  }

  initHeroVideoQuality();
  absolutizeHotelSiteConceptMedia();
  void initRandomGuestReviews();

  const filtersController = initFilters();
  initSearchBar(filtersController);
  initCategoryPicks(filtersController);
  hydrateHomeCatalog(filtersController);
  hydrateKvartiraCatalog();
  hydrateHotelPage();
})();
