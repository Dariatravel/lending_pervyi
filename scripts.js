(() => {
  const body = document.body;
  if (!body) return;
  const METRIKA_ID = 108214677;
  const GA4_ID = "G-MZ2NTRDDJ5";
  const SITE_CANONICAL_ORIGIN = "https://абхазберег.рф";
  const PUNY_SITE_HOST = "xn--80aacbklan7f0b.xn--p1ai";
  const PUNY_SITE_ORIGINS = [
    `https://${PUNY_SITE_HOST}`,
    `http://${PUNY_SITE_HOST}`,
  ];

  function buildPublicShareUrl(pathname = window.location.pathname, search = window.location.search) {
    const path = pathname || "/";
    return `${SITE_CANONICAL_ORIGIN}${path}${search || ""}`;
  }

  function normalizePublicUrlText(raw) {
    let text = String(raw || "");
    PUNY_SITE_ORIGINS.forEach((origin) => {
      text = text.split(origin).join(SITE_CANONICAL_ORIGIN);
    });
    return text;
  }

  async function copyPublicUrl(triggerBtn, copiedLabel = "Ссылка скопирована", defaultLabel = "") {
    const url = buildPublicShareUrl();
    const original = triggerBtn?.textContent || defaultLabel;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        window.prompt("Скопируйте ссылку:", url);
        return;
      }
      if (triggerBtn) {
        triggerBtn.textContent = copiedLabel;
        window.setTimeout(() => {
          triggerBtn.textContent = original;
        }, 2200);
      }
    } catch (error) {
      window.prompt("Скопируйте ссылку:", url);
    }
  }

  function initCanonicalUrlDisplay() {
    if (window.location.hostname !== PUNY_SITE_HOST) return;
    const nextUrl = `${window.location.pathname || "/"}${window.location.search || ""}${window.location.hash || ""}`;
    try {
      window.history.replaceState(window.history.state, "", nextUrl);
    } catch (error) {
      /* ignore unsupported replaceState */
    }
  }

  function initPublicUrlCopyNormalization() {
    document.addEventListener("copy", (event) => {
      const selection = window.getSelection?.()?.toString?.() || "";
      if (!selection.includes(PUNY_SITE_HOST)) return;
      const normalized = normalizePublicUrlText(selection);
      if (normalized === selection) return;
      event.preventDefault();
      event.clipboardData?.setData("text/plain", normalized);
    });
  }

  function initListingPageShareLink() {
    const match = window.location.pathname.match(/^\/(?:hotels|kvartira)\/([^/]+)\/?$/);
    if (!match || document.getElementById("copy-listing-link")) return;

    const topline = document.querySelector(".hotel-card__topline");
    const catalogBtn = topline?.querySelector(".save-button");
    if (!topline || !catalogBtn) return;

    let actions = topline.querySelector(".hotel-card__topline-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "hotel-card__topline-actions";
      catalogBtn.replaceWith(actions);
      actions.appendChild(catalogBtn);
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "save-button";
    btn.id = "copy-listing-link";
    btn.textContent = "Скопировать ссылку";
    btn.addEventListener("click", () => {
      void copyPublicUrl(btn);
    });
    actions.insertBefore(btn, catalogBtn);
  }

  initCanonicalUrlDisplay();
  initPublicUrlCopyNormalization();

  function setupMetrikaQueue() {
    window.ym =
      window.ym ||
      function metrikaShim(...args) {
        (window.ym.a = window.ym.a || []).push(args);
      };
    window.ym.l = window.ym.l || Date.now();
  }

  function initMetrika() {
    setupMetrikaQueue();
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

  function setupGA4Queue() {
    window.dataLayer = window.dataLayer || [];
    window.gtag =
      window.gtag ||
      function gtagShim() {
        window.dataLayer.push(arguments);
      };
  }

  function initGA4() {
    setupGA4Queue();
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

  function initDeferredAnalytics() {
    setupMetrikaQueue();
    setupGA4Queue();

    let started = false;
    const events = ["scroll", "pointerdown", "keydown", "touchstart"];
    const cleanup = () => {
      events.forEach((eventName) => {
        window.removeEventListener(eventName, startAnalytics);
      });
    };
    const startAnalytics = () => {
      if (started) return;
      started = true;
      cleanup();
      initMetrika();
      initGA4();
    };

    events.forEach((eventName) => {
      window.addEventListener(eventName, startAnalytics, { once: true, passive: true });
    });

    window.setTimeout(() => {
      if ("requestIdleCallback" in window) {
        window.requestIdleCallback(startAnalytics, { timeout: 4000 });
      } else {
        startAnalytics();
      }
    }, 12000);
  }

  initDeferredAnalytics();

  const CDN_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media/media";
  const ASSET_VERSION = "202607190020";
  const CATALOG_INDEX_URL = `/data/catalog-index.json?v=${ASSET_VERSION}`;
  const SCREENSHOT_REVIEW_GLOBAL_URL = `${CDN_MEDIA_BASE}/reviews/global.json?v=${ASSET_VERSION}`;
  /** Контракт `data-filter-*` и порядок URL не меняем; здесь описание групп для UI и поддержки. */
  const FILTER_CONFIG = {
    /** Отдельный URL-парам (hotel / guesthouse / cabin), не смешиваем с группами `data-filter-*` на карточках. Состояние категории живёт рядом с группами в createFilterStore (committedCat / draftCat). */
    catalogParamKey: "catalog",
    groupOrder: ["distance", "food", "price", "city", "beach", "room", "stay"],
    /** OR внутри группы по умолчанию; для room/stay — AND (все выбранные чипы). Между группами — AND. */
    combineWithinGroup: "any",
    combineWithinGroupByGroup: {
      room: "all",
      stay: "all",
    },
    combineAcrossGroups: "all",
    groupLabels: {
      distance: "Расстояние до пляжа",
      food: "Питание",
      price: "Бюджет",
      city: "Город",
      beach: "Пляж",
      room: "Номер и удобства",
      stay: "Формат размещения",
    },
  };

  const FILTER_GROUPS = FILTER_CONFIG.groupOrder;

  const SELECTION_CITY_ORDER = [
    "ldzaa",
    "pitsunda",
    "gagra",
    "alakhadzy",
    "gudauta",
    "new-afon",
    "sukhum",
    "tsandripsh",
  ];

  const SELECTION_CITY_LABELS = {
    ldzaa: "ЛДЗАА",
    pitsunda: "ПИЦУНДА",
    gagra: "ГАГРА",
    alakhadzy: "АЛАХАДЗЫ",
    gudauta: "ГУДАУТА",
    "new-afon": "НОВЫЙ АФОН",
    sukhum: "СУХУМ",
    tsandripsh: "ЦАНДРИПШ",
    other: "ДРУГИЕ ЛОКАЦИИ",
  };

  function isKvartiraCatalogCard(cardEl) {
    if (!cardEl) return false;
    const kind = cardEl.dataset.listingKind;
    if (kind === "kvartira") return true;
    if (kind === "hotel") return false;
    return /^\/kvartira\//.test(String(cardEl.getAttribute("href") || ""));
  }

  function isHotelCatalogCard(cardEl) {
    return !isKvartiraCatalogCard(cardEl);
  }

  function catalogCardCityKey(cardEl) {
    const cityRaw = String(cardEl.dataset.filterCity || "");
    const first = cityRaw.split("|").map((part) => part.trim()).find(Boolean);
    if (first && SELECTION_CITY_ORDER.includes(first)) return first;
    const mapCity = cardEl.querySelector("[data-map-city]")?.dataset.mapCity;
    if (mapCity && SELECTION_CITY_ORDER.includes(mapCity)) return mapCity;
    return "other";
  }

  function catalogCardTitleKey(cardEl) {
    const h3 = cardEl.querySelector("h3");
    return (h3?.textContent || "").trim().toLowerCase();
  }

  function variantLabelRu(count) {
    const n = Number(count);
    if (!Number.isFinite(n) || n <= 0) return "0 вариантов";
    const mod100 = n % 100;
    const mod10 = n % 10;
    if (mod100 >= 11 && mod100 <= 14) return `${n} вариантов`;
    if (mod10 === 1) return `${n} вариант`;
    if (mod10 >= 2 && mod10 <= 4) return `${n} варианта`;
    return `${n} вариантов`;
  }

  /** Режим индивидуальной подборки: витрина как у /podborki/, карточки временно переносятся из #catalog-grid. */
  function attachSelectionPodborkaView(spec) {
    const {
      grid,
      heroEl,
      viewEl,
      titleEl,
      countEl,
      shareBtn,
      shareHeroBtn,
      editFiltersBtn,
      openFiltersModal,
      buildSelectionTitle,
    } = spec;

    let active = false;
    const cardAnchorIndex = new WeakMap();

    function rememberAnchors() {
      if (!grid) return;
      Array.from(grid.querySelectorAll(".catalog-card")).forEach((card, index) => {
        card.dataset.catalogAnchorIndex = String(index);
        cardAnchorIndex.set(card, index);
      });
    }

    function restoreCardsToGrid() {
      if (!grid) return;
      const cards = Array.from(document.querySelectorAll("#catalog-grid .catalog-card, #selection-podborka-view .catalog-card"));
      cards.sort((a, b) => {
        const ai = Number(a.dataset.catalogAnchorIndex || cardAnchorIndex.get(a) || 0);
        const bi = Number(b.dataset.catalogAnchorIndex || cardAnchorIndex.get(b) || 0);
        return ai - bi;
      });
      cards.forEach((card) => {
        card.classList.remove("podborki-catalog-card");
        card.querySelector(".catalog-card__badge--rank")?.remove();
        if (card.parentElement !== grid) grid.appendChild(card);
      });
      if (viewEl) viewEl.replaceChildren();
    }

    function setRankBadge(card, rank) {
      const wrap = card.querySelector(".catalog-card__media-wrap");
      if (!wrap) return;
      let badge = wrap.querySelector(".catalog-card__badge--rank");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "catalog-card__badge catalog-card__badge--rank";
        wrap.insertBefore(badge, wrap.firstChild);
      }
      badge.textContent = String(rank);
      badge.setAttribute("aria-label", `Место в подборке — ${rank}`);
    }

    function appendRegionBlock(parent, label, cards, startRank) {
      if (!cards.length) return startRank;
      const region = document.createElement("h2");
      region.className = "podborki-region";
      region.textContent = label;
      parent.appendChild(region);

      const regionGrid = document.createElement("div");
      regionGrid.className = "catalog-grid podborki-catalog-grid";
      let rank = startRank;
      cards.forEach((card) => {
        rank += 1;
        card.classList.add("podborki-catalog-card");
        setRankBadge(card, rank);
        regionGrid.appendChild(card);
      });
      parent.appendChild(regionGrid);
      return rank;
    }

    function citySortIndex(card) {
      const key = catalogCardCityKey(card);
      const idx = SELECTION_CITY_ORDER.indexOf(key);
      return idx >= 0 ? idx : SELECTION_CITY_ORDER.length;
    }

    function buildView(visibleCards) {
      if (!viewEl) return;
      viewEl.replaceChildren();

      const sorted = [...visibleCards].sort((a, b) => {
        const cityDiff = citySortIndex(a) - citySortIndex(b);
        if (cityDiff !== 0) return cityDiff;
        return catalogCardTitleKey(a).localeCompare(catalogCardTitleKey(b), "ru");
      });

      let rank = 0;
      const cardsByCity = new Map();
      sorted.forEach((card) => {
        const key = catalogCardCityKey(card);
        if (!cardsByCity.has(key)) cardsByCity.set(key, []);
        cardsByCity.get(key).push(card);
      });

      [...SELECTION_CITY_ORDER, "other"].forEach((cityKey) => {
        const group = cardsByCity.get(cityKey) || [];
        if (!group.length) return;
        rank = appendRegionBlock(
          viewEl,
          SELECTION_CITY_LABELS[cityKey] || SELECTION_CITY_LABELS.other,
          group,
          rank
        );
      });
    }

    function setShareButtonsVisible(show) {
      [shareBtn, shareHeroBtn].forEach((btn) => {
        if (!btn) return;
        btn.hidden = !show;
      });
    }

    async function copyShareLink(triggerBtn) {
      await copyPublicUrl(triggerBtn, "Ссылка скопирована", triggerBtn?.textContent || "");
    }

    function wireShareButtons() {
      [shareBtn, shareHeroBtn].forEach((btn) => {
        if (!btn || btn.dataset.shareWired === "1") return;
        btn.dataset.shareWired = "1";
        btn.addEventListener("click", () => {
          void copyShareLink(btn);
        });
      });
    }

    function wireEditFilters() {
      if (!editFiltersBtn || editFiltersBtn.dataset.editWired === "1") return;
      editFiltersBtn.dataset.editWired = "1";
      editFiltersBtn.addEventListener("click", () => {
        if (typeof openFiltersModal === "function") openFiltersModal();
      });
    }

    function wireScrollMemory() {
      if (viewEl?.dataset.scrollWired === "1") return;
      if (viewEl) viewEl.dataset.scrollWired = "1";
      viewEl?.addEventListener("click", (event) => {
        if (!active) return;
        if (!event.target.closest(".catalog-card")) return;
        try {
          sessionStorage.setItem("abhaz:selectionScroll", String(window.scrollY));
        } catch (storageError) {
          /* ignore quota / private mode */
        }
      });
    }

    function restoreScrollFromSession() {
      try {
        const raw = sessionStorage.getItem("abhaz:selectionScroll");
        if (!raw) return;
        const y = Number.parseInt(raw, 10);
        if (!Number.isFinite(y)) return;
        window.requestAnimationFrame(() => window.scrollTo({ top: y, behavior: "auto" }));
      } catch (storageError) {
        /* ignore */
      }
    }

    function sync(totalMatching, pins) {
      const shouldShow = pins > 0 && totalMatching > 0;
      if (!shouldShow) {
        if (active) {
          active = false;
          document.body.classList.remove("is-selection-podborka");
          restoreCardsToGrid();
          if (heroEl) heroEl.hidden = true;
          if (viewEl) viewEl.hidden = true;
          setShareButtonsVisible(false);
        }
        return;
      }

      const visibleCards = Array.from(grid?.querySelectorAll(".catalog-card") || []).filter((card) => !card.hidden);
      if (!visibleCards.length) {
        if (active) {
          active = false;
          document.body.classList.remove("is-selection-podborka");
          restoreCardsToGrid();
          if (heroEl) heroEl.hidden = true;
          if (viewEl) viewEl.hidden = true;
          setShareButtonsVisible(false);
        }
        return;
      }

      if (titleEl && typeof buildSelectionTitle === "function") {
        titleEl.textContent = buildSelectionTitle();
      }
      if (countEl) countEl.textContent = variantLabelRu(totalMatching);

      restoreCardsToGrid();
      buildView(visibleCards);

      active = true;
      document.body.classList.add("is-selection-podborka");
      if (heroEl) heroEl.hidden = false;
      if (viewEl) viewEl.hidden = false;
      setShareButtonsVisible(true);
      wireShareButtons();
      wireEditFilters();
      wireScrollMemory();
      restoreScrollFromSession();
    }

    return { rememberAnchors, sync, restoreCardsToGrid };
  }

  const BEACH_FILTERS = {
    SAND_LDZAA: "sand-ldzaa",
    SAND_SUKHUM: "sand-sukhum",
    PINE_PEBBLE_LDZAA_PITSUNDA: "pine-pebble-ldzaa-pitsunda",
    PITSUNDA_BAY_MIXED: "pitsunda-bay-mixed",
    PEBBLE: "pebble",
  };
  const FEMALE_REVIEW_NAMES = [
    "Анна",
    "Марина",
    "Елена",
    "Ольга",
    "Ирина",
    "Наталья",
    "Алина",
    "Юлия",
    "Светлана",
    "Екатерина",
    "Дарья",
    "Виктория",
    "Татьяна",
    "Ксения",
    "Людмила",
    "Полина",
    "Яна",
    "Вероника",
    "Алёна",
    "София",
  ];
  const MALE_REVIEW_NAMES = [
    "Андрей",
    "Максим",
    "Сергей",
    "Алексей",
    "Павел",
    "Илья",
    "Михаил",
    "Егор",
    "Роман",
    "Дмитрий",
    "Никита",
    "Владимир",
    "Артём",
    "Константин",
    "Олег",
    "Игорь",
    "Денис",
    "Кирилл",
    "Виталий",
    "Юрий",
  ];
  const GENERIC_REVIEW_PARTS = {
    female: {
      intros: [
        "Ехала в Абхазию впервые и очень переживала из-за выбора жилья.",
        "Долго сомневалась, какой район нам подойдёт, потому что в Абхазии раньше не была.",
        "Для меня было важно не ошибиться с первым отдыхом в Абхазии.",
        "Боялась, что на месте всё будет совсем не так, как на фото.",
        "Перед поездкой было много тревоги: где удобнее жить, какой пляж выбрать и как не промахнуться с объектом.",
        "Искала спокойный вариант отдыха и очень не хотела нарваться на разочарование.",
        "Сначала переживала, что без личной рекомендации выбрать жильё будет почти невозможно.",
        "Мы планировали первую поездку и я боялась, что ошибусь с локацией.",
        "Выбирала жильё долго, потому что хотелось отдыха без неприятных сюрпризов.",
        "Больше всего волновалась, чтобы описание объекта совпало с реальностью.",
      ],
      specifics: [
        "Помогло, что всё было объяснено человеческим языком, без рекламного тумана.",
        "Очень ценно, что заранее объяснили разницу между районами и не отправляли выбирать вслепую.",
        "Было удобно, что на странице сразу понятны пляж, расстояние до моря и общий формат отдыха.",
        "Мне понравилось, что при подборе учли именно бытовые детали, а не только красивые фото.",
        "Решающим стало то, что здесь честно показывают нюансы, а не скрывают их за красивыми формулировками.",
        "После консультации и описания на сайте стало понятно, какой вариант реально подходит именно нам.",
        "Особенно помогло, что было легко сравнить районы и быстро отсечь неудобные варианты.",
        "Сайт оказался полезным именно в том, что снимает тревогу ещё до бронирования.",
        "Подборка выглядела не как случайный набор объектов, а как понятная рекомендация под наш отдых.",
        "Очень удобно, когда сразу видны не только плюсы, но и важные практические детали.",
      ],
      details: [
        "Сразу стало понятно, где лучше остановиться с ребёнком, а где комфортнее ехать вдвоём.",
        "Особенно помогло, что были честно расписаны пляж, дорога и сам характер района.",
        "После просмотра не осталось ощущения, что нужно ещё где-то отдельно перепроверять базовые вещи.",
        "Удобно, что можно было быстро понять, будет ли там спокойно вечером и удобно днём.",
        "Очень помогло, что на странице были не только фото, но и понятное объяснение, кому подойдёт место.",
        "Мне было важно заранее понять бытовые нюансы, и именно это здесь оказалось хорошо раскрыто.",
        "По описанию стало ясно, какой это отдых по атмосфере, а не только по формальным параметрам.",
        "Сильнее всего помогло то, что здесь объясняют выбор простым и человеческим языком.",
        "Было легко представить саму поездку целиком: район, пляж, путь до моря и формат проживания.",
        "Очень ценно, когда сразу понимаешь, подходит ли место для спокойного отдыха без лишней суеты.",
      ],
      endings: [
        "В итоге отдых прошёл спокойно, а на месте всё оказалось именно таким, как было обещано.",
        "Благодаря этому решение далось легко, и поездка получилась без лишних нервов.",
        "На месте не было неприятных сюрпризов, и за это я особенно благодарна.",
        "После такого выбора чувствуешь не тревогу, а уверенность, что едешь в понятное место.",
        "Именно такого ощущения надёжности обычно не хватает на обычных сайтах бронирования.",
        "Для первой поездки это оказалось самым ценным — не гадать, а понимать, куда едешь.",
        "Очень рада, что в итоге выбрали именно через такой формат подбора, а не вслепую.",
        "Это тот случай, когда описание действительно помогает принять верное решение.",
        "После поездки осталось ощущение, что нас вели к подходящему варианту очень аккуратно и честно.",
        "Теперь уже спокойно рекомендую такой подход знакомым, потому что он реально работает.",
      ],
    },
    male: {
      intros: [
        "Ехал в Абхазию впервые и переживал, что ошибусь с районом и жильём.",
        "С самого начала не хотел бронировать вслепую, потому что до этого в Абхазии не был.",
        "Для меня было важно понять, где отдых будет действительно удобным, а не только красивым на фото.",
        "Сначала сомневался, что по интернету вообще можно выбрать нормальный вариант без ошибок.",
        "Больше всего опасался, что на месте окажется совсем другой уровень, чем обещали.",
        "Хотелось избежать типичной истории, когда фото красивые, а реальность потом разочаровывает.",
        "Искал не просто жильё, а понятный вариант отдыха без лишнего стресса.",
        "Главный вопрос был в том, какой район нам подойдёт и не придётся ли потом жалеть о выборе.",
        "Перед поездкой было много сомнений, потому что регион для нас был новым.",
        "Решение далось не сразу, потому что хотелось заранее понимать все важные детали.",
      ],
      specifics: [
        "Понравилось, что здесь помогают не просто выбрать объект, а разобраться в самой логике отдыха.",
        "Сильнее всего помогло то, что на сайте всё разложено по делу: пляж, дорога, формат, нюансы.",
        "Было важно, что никто не пытался продавить первый попавшийся вариант, а реально помогли выбрать.",
        "Очень удобно, когда в описании есть не только красивые слова, но и полезные бытовые детали.",
        "Всё подано так, что решение принимаешь спокойно и понимаешь, почему этот вариант тебе подходит.",
        "Отдельный плюс за честность: сразу видно не только преимущества, но и ограничения объекта.",
        "После такого подхода выбор ощущается не случайным, а действительно обоснованным.",
        "Нравится, что здесь думают не только про бронь, но и про реальный комфорт на месте.",
        "Сайт оказался полезным именно потому, что убирает неопределённость до поездки.",
        "Решающим стало то, что здесь есть ощущение живой экспертной помощи, а не просто витрины.",
      ],
      details: [
        "На этапе выбора это сняло половину вопросов по району, пляжу и бытовым условиям.",
        "По итогу было понятно не только что бронируешь, но и как будет устроен сам отдых.",
        "Особенно полезно, что здесь можно быстро понять разницу между локациями и форматами размещения.",
        "Понравилось, что описание помогает оценить не только сам объект, но и весь сценарий поездки.",
        "После просмотра уже не оставалось ощущения, что едешь почти вслепую.",
        "На практике именно эта конкретика по быту и логистике оказалась самой полезной.",
        "Важно, что здесь легко заранее оценить, насколько отдых будет спокойным и удобным.",
        "Сайт помог не тратить время на неподходящие варианты и сразу сузить выбор до адекватных.",
        "Сильнее всего помогло то, что информация подана структурно, без воды и рекламных преувеличений.",
        "На фоне обычных каталогов здесь гораздо легче понять, чего ждать от места в реальности.",
      ],
      endings: [
        "В результате отдых прошёл именно так, как мы рассчитывали, без неприятных неожиданностей.",
        "После такой подготовки на месте уже не тратишь силы на решение лишних проблем.",
        "Для первой поездки такой формат подбора оказался максимально правильным.",
        "Осталось ощущение, что выбор был сделан не наугад, а на основе нормальной и честной информации.",
        "Теперь понимаю, насколько спокойнее ехать, когда заранее всё разложено по полочкам.",
        "Именно эта ясность и помогла нам нормально подготовиться к поездке.",
        "Редкий случай, когда описание на сайте действительно помогает, а не только украшает объект.",
        "Такой подход реально экономит время, силы и убирает лишнюю тревогу перед дорогой.",
        "После поездки осталось хорошее впечатление не только от объекта, но и от самого процесса выбора.",
        "В следующий раз тоже буду ориентироваться на такой формат подбора, а не на случайные карточки.",
      ],
    },
  };
  let catalogIndexPromise = null;
  let screenshotReviewBank = null;
  let screenshotReviewBankPromise = null;

  const lightbox = document.createElement("div");
  lightbox.className = "lightbox";
  lightbox.setAttribute("hidden", "");
  lightbox.innerHTML = `
    <button class="lightbox__close" type="button" aria-label="Закрыть">×</button>
    <button class="lightbox__nav lightbox__nav--prev" type="button" aria-label="Предыдущее фото">‹</button>
    <button class="lightbox__nav lightbox__nav--next" type="button" aria-label="Следующее фото">›</button>
    <div class="lightbox__stage">
      <img class="lightbox__image" alt="" hidden />
      <video class="lightbox__video" controls playsinline preload="metadata" hidden></video>
    </div>
    <p class="lightbox__counter" aria-live="polite"></p>
  `;
  body.appendChild(lightbox);

  const lightboxImage = lightbox.querySelector(".lightbox__image");
  const lightboxVideo = lightbox.querySelector(".lightbox__video");
  const lightboxCounter = lightbox.querySelector(".lightbox__counter");
  const closeButton = lightbox.querySelector(".lightbox__close");
  const prevButton = lightbox.querySelector(".lightbox__nav--prev");
  const nextButton = lightbox.querySelector(".lightbox__nav--next");
  lightboxVideo?.addEventListener("play", pauseInlineGalleryVideos);
  let galleryItems = [];
  let galleryIndex = 0;
  let galleryTouchStartX = 0;

  function normalizeGallerySrc(src) {
    const raw = String(src || "").trim();
    if (!raw) return "";
    try {
      const url = new URL(raw, window.location.origin);
      return decodeURIComponent(url.pathname).toLowerCase();
    } catch (error) {
      return decodeURIComponent(raw.split("?")[0]).toLowerCase();
    }
  }

  function gallerySrcFromImage(image) {
    if (!image) return "";
    return image.currentSrc || image.src || "";
  }

  function gallerySrcFromVideo(video) {
    if (!video) return "";
    return video.querySelector("source")?.getAttribute("src") || video.getAttribute("src") || "";
  }

  function galleryItemFromNode(node) {
    if (!node) return null;

    if (node.matches("img")) {
      const src = gallerySrcFromImage(node);
      if (!src) return null;
      return {
        type: "image",
        src,
        alt: node.getAttribute("alt") || "",
        key: normalizeGallerySrc(src),
      };
    }

    if (node.matches("video")) {
      const src = gallerySrcFromVideo(node);
      if (!src) return null;
      return {
        type: "video",
        src,
        alt: node.getAttribute("aria-label") || "Видео объекта",
        key: normalizeGallerySrc(src),
      };
    }

    if (node.matches(".video-embed")) {
      const preview = node.querySelector(".local-video-preview");
      const video = node.querySelector("video.local-video");
      const link = node.querySelector(".video-link");
      const src = gallerySrcFromImage(preview) || gallerySrcFromVideo(video) || link?.href || "";
      if (!src) return null;
      const isVideo = /\.(mp4|webm|mov)(\?|$)/i.test(src) || Boolean(video);
      return {
        type: isVideo ? "video" : "image",
        src,
        alt: preview?.getAttribute("alt") || "Видео объекта",
        key: normalizeGallerySrc(src),
      };
    }

    return null;
  }

  function collectObjectGalleryItems() {
    const grids = document.querySelectorAll(
      ".hotel-site-concept .media-grid, .hotel-site-concept .comment-media-grid, .hotel-site-concept .comment-review-grid, .blog-article__media-gallery"
    );
    if (!grids.length) return [];

    const items = [];
    const seen = new Set();
    Array.from(grids).forEach((grid) => {
      grid.querySelectorAll(":scope > img, :scope > video, :scope > .video-embed, figure img, figure video").forEach((node) => {
        if (node.matches("img.local-video-preview") && node.closest(".video-embed")) return;
        const item = galleryItemFromNode(node);
        if (!item?.key || seen.has(item.key)) return;
        seen.add(item.key);
        items.push(item);
      });
    });

    return items;
  }

  function findGalleryIndexByKey(key) {
    if (!key) return 0;
    const index = galleryItems.findIndex((item) => item.key === key);
    return index >= 0 ? index : 0;
  }

  function updateGalleryNavState() {
    const hasMany = galleryItems.length > 1;
    if (prevButton) prevButton.hidden = !hasMany;
    if (nextButton) nextButton.hidden = !hasMany;
    if (lightboxCounter) {
      lightboxCounter.textContent = galleryItems.length
        ? `${galleryIndex + 1} / ${galleryItems.length}`
        : "";
    }
  }

  function pauseLightboxVideo() {
    if (!lightboxVideo) return;
    try {
      lightboxVideo.pause();
      lightboxVideo.currentTime = 0;
    } catch (error) {
      /* ignore */
    }
    lightboxVideo.removeAttribute("src");
    while (lightboxVideo.firstChild) {
      lightboxVideo.removeChild(lightboxVideo.firstChild);
    }
    lightboxVideo.removeAttribute("poster");
    lightboxVideo.removeAttribute("aria-label");
    try {
      lightboxVideo.load();
    } catch (error) {
      /* ignore */
    }
    lightboxVideo.hidden = true;
  }

  function pauseInlineGalleryVideos() {
    document
      .querySelectorAll(
        ".hotel-site-concept .media-grid video, .hotel-site-concept .hotel-media-section video, .hotel-site-concept .hotel-card__gallery video, .hotel-site-concept .comment-media-grid video, .hotel-site-concept .comment-review-grid video, .blog-article__media-gallery video"
      )
      .forEach((node) => {
        try {
          node.pause();
          node.currentTime = 0;
        } catch (error) {
          /* ignore */
        }
      });
  }

  /** Клик по полоске native controls — только inline-воспроизведение, без lightbox. */
  function isVideoControlsClick(video, event) {
    if (!video?.controls || !event) return false;
    const rect = video.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    const y = event.clientY - rect.top;
    const controlBand = Math.min(56, Math.max(36, rect.height * 0.28));
    return y >= rect.height - controlBand;
  }

  function openInlineGalleryVideoLightbox(video) {
    if (!video) return;
    const src = gallerySrcFromVideo(video);
    if (!src) return;
    pauseInlineGalleryVideos();
    openGalleryLightboxAtKey(normalizeGallerySrc(src));
  }

  function renderGalleryItem(index) {
    if (!galleryItems.length) return;
    galleryIndex = (index + galleryItems.length) % galleryItems.length;
    const item = galleryItems[galleryIndex];
    if (!item || !lightboxImage) return;

    pauseLightboxVideo();
    lightboxImage.hidden = true;
    lightboxImage.removeAttribute("src");
    lightboxImage.alt = "";

    if (item.type === "video" && lightboxVideo) {
      const source = document.createElement("source");
      source.src = item.src;
      source.type = "video/mp4";
      lightboxVideo.appendChild(source);
      lightboxVideo.setAttribute("aria-label", item.alt || "Видео объекта");
      lightboxVideo.hidden = false;
      const itemKey = normalizeGallerySrc(item.src);
      const gridVideo = Array.from(
        document.querySelectorAll(
          ".hotel-site-concept .media-grid video.local-video, .hotel-site-concept .comment-media-grid video.local-video, .hotel-site-concept .comment-review-grid video.local-video, .blog-article__media-gallery video"
        )
      ).find((node) => {
        const src = gallerySrcFromVideo(node);
        return normalizeGallerySrc(src) === itemKey;
      });
      if (gridVideo?.poster) {
        lightboxVideo.poster = gridVideo.poster;
      } else {
        lightboxVideo.removeAttribute("poster");
      }
      lightboxVideo.load();
      if (!lightboxVideo.poster) wireLocalVideoPoster(lightboxVideo);
    } else {
      lightboxImage.src = item.src;
      lightboxImage.alt = item.alt || "";
      lightboxImage.hidden = false;
    }

    updateGalleryNavState();
  }

  function openGalleryLightbox(startIndex = 0) {
    galleryItems = collectObjectGalleryItems();
    if (!galleryItems.length) return;
    pauseInlineGalleryVideos();
    renderGalleryItem(startIndex);
    lightbox.removeAttribute("hidden");
    body.classList.add("modal-open");
  }

  function openGalleryLightboxAtKey(key) {
    galleryItems = collectObjectGalleryItems();
    if (!galleryItems.length) return;
    openGalleryLightbox(findGalleryIndexByKey(key));
  }

  const openLightbox = (src, alt) => {
    if (!src) return;
    openGalleryLightboxAtKey(normalizeGallerySrc(src));
    if (!galleryItems.length && lightboxImage) {
      galleryItems = [{ type: "image", src, alt: alt || "", key: normalizeGallerySrc(src) }];
      galleryIndex = 0;
      lightboxImage.src = src;
      lightboxImage.alt = alt || "";
      lightboxImage.hidden = false;
      pauseLightboxVideo();
      updateGalleryNavState();
      lightbox.removeAttribute("hidden");
      body.classList.add("modal-open");
    }
  };

  function stepGalleryLightbox(step) {
    if (!galleryItems.length || lightbox.hasAttribute("hidden")) return;
    renderGalleryItem(galleryIndex + step);
  }

  const closeLightbox = () => {
    lightbox.setAttribute("hidden", "");
    body.classList.remove("modal-open");
    galleryItems = [];
    galleryIndex = 0;
    if (lightboxImage) {
      lightboxImage.src = "";
      lightboxImage.alt = "";
      lightboxImage.hidden = true;
    }
    pauseLightboxVideo();
    if (lightboxCounter) lightboxCounter.textContent = "";
    if (prevButton) prevButton.hidden = true;
    if (nextButton) nextButton.hidden = true;
  };

  function hashString(value) {
    const text = String(value || "");
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function createSeededRandom(seedInput) {
    let seed = hashString(seedInput) || 1;
    return () => {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function shuffleCopy(items, randomizer = Math.random) {
    const list = Array.isArray(items) ? [...items] : [];
    for (let index = list.length - 1; index > 0; index -= 1) {
      const nextIndex = Math.floor(randomizer() * (index + 1));
      [list[index], list[nextIndex]] = [list[nextIndex], list[index]];
    }
    return list;
  }

  function cleanReviewFact(value) {
    return String(value || "")
      .replace(/[📍🏖🏝👥]/g, "")
      .replace(/<br\s*\/?>/gi, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[.;:,]+$/g, "");
  }

  function capitalizeFirst(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function sentence(value) {
    const text = String(value || "").trim().replace(/\s+/g, " ");
    if (!text) return "";
    return /[.!?…]$/.test(text) ? text : `${text}.`;
  }

  const REVIEW_START_WORDS = [
    "отдыхали",
    "отель",
    "отели",
    "мы",
    "в ",
    "на ",
    "прекрас",
    "удобн",
    "чист",
    "понрав",
    "рекоменд",
    "ехали",
    "приехали",
    "бронировали",
    "остановились",
    "жили",
    "вернусь",
    "вернемся",
    "планируем",
    "искали",
    "выбрали",
    "побывали",
    "провели",
    "остались",
    "получили",
    "всё",
    "все ",
    "есть ",
    "очень ",
    "шикар",
    "замечат",
    "отличн",
    "хорош",
    "уютн",
    "гостеприим",
    "территор",
    "номер",
    "море",
    "пляж",
    "бассейн",
    "персонал",
    "хозяйк",
    "администрац",
    "расположен",
    "рядом",
    "до моря",
  ];

  function looksLikeReviewStart(value) {
    const lower = String(value || "").toLowerCase();
    return REVIEW_START_WORDS.some((marker) => lower.startsWith(marker));
  }

  function greetingAfterName(value) {
    return /^(?:спасибо|добрый|даша|дарья|здравствуйте|хочу|ну\s+вот|нам\s|большое\s+спасибо|огромное\s+спасибо)/i.test(
      String(value || "").trim()
    );
  }

  function stripLeadingNamePrefix(value) {
    let text = String(value || "");
    const namePrefix =
      /^\s*(?:ОБ\s+)?(?:[А-ЯЁ][а-яё]+|[A-Z][A-Za-z]{1,}(?:-[A-Z][A-Za-z]{1,})?)(?:\s+(?:[А-ЯЁ][а-яё]+|[A-Z][A-Za-z]{1,}(?:-[A-Z][A-Za-z]{1,})?)){0,2}\s+(?=спасибо|добрый|даша|дарья|здравствуйте|хочу|ну\s+вот|нам\s|большое\s+спасибо|огромное\s+спасибо)/i;

    while (true) {
      const match = text.match(namePrefix);
      if (!match) break;
      const remainder = text.slice(match[0].length).trim();
      if (!remainder || looksLikeReviewStart(remainder)) break;
      text = remainder;
    }
    return text.trim();
  }

  function truncateSocialNoise(value) {
    return String(value || "")
      .split(/(?:Abhazize|Alkhaziae|ОТЕЛИ\|ЖИЛЬЕ\|СНЯТ[ЫЬ]ОТ|G Google|захарод в сервисе)/i)[0]
      .trim();
  }

  function truncateOwnerReply(value) {
    const text = String(value || "");
    const match = text.match(
      /(?:^|[.!?…]\s+)(?:[А-ЯЁ][а-яё]+),?\s*здравствуйте!\s*Большое спасибо за отзыв!?/i
    );
    if (!match || match.index == null) return text.trim();
    return text.slice(0, match.index).trim();
  }

  function dedupeRepeatedLead(value) {
    const text = String(value || "").trim();
    const words = text.split(/\s+/);
    if (words.length < 12) return text;
    const lead = words.slice(0, 8).join(" ").toLowerCase();
    const second = text.toLowerCase().indexOf(lead, lead.length);
    if (second > 40) return text.slice(0, second).trim();
    return text;
  }

  function cleanReviewTextForDisplay(value) {
    let text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";

    text = text.replace(/^\s*[+»«"']+\s*/, "");
    text = text.replace(/(?:раскрыть\s+детали|что\s+было\s+хорошо|подписаться)/gi, " ");
    text = text.replace(/оценка\s*wi[\s-]*fi[^.?!]*[.?!]?/gi, " ");
    text = text.replace(/\b\d+\s*уровня\b/gi, " ");

    const prefixPatterns = [
      /^\s*\d{1,2}\s*(?:превосходно|отлично|хорошо|супер)\s*/i,
      /^\s*\d{1,2}\s+[а-яё]+\s*/i,
      /^\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*/i,
      /^\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){0,2}\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*/i,
      /^\s*[А-ЯЁ][а-яё]+[:,]?\s*добрый\s+(?:день|вечер|утро),?\s*дарья!?\.?\s*/i,
      /^\s*добрый\s+(?:день|вечер|утро),?\s*дарья!?\.?\s*/i,
      /^\s*[А-ЯA-Z]\s+(?=[А-ЯЁ][а-яё]+)/i,
      /^\s*ОБ\s+\d{1,2}\s+[а-яё]+\s*/i,
    ];

    let changed = true;
    while (changed) {
      changed = false;
      for (const pattern of prefixPatterns) {
        const next = text.replace(pattern, "");
        if (next !== text) {
          text = next.trim();
          changed = true;
        }
      }
    }

    text = stripLeadingNamePrefix(text);

    const leadingThanks =
      /^\s*(?:спасибо\s+большое\s*!?\s*|большое\s+спасибо\s*!?\s*|огромное\s+спасибо\s*!?\s*|даша,?\s+спасибо\s+вам\s+огромное\s*!+\s*|дарья,?\s+|добрый\s+(?:день|вечер|утро)[.!?]?\s*(?:дарья[!]?[,]?\s*)?)/i;
    changed = true;
    while (changed) {
      changed = false;
      const next = text.replace(leadingThanks, "");
      if (next !== text) {
        text = next.trim();
        changed = true;
      }
    }

    text = truncateSocialNoise(text);
    text = truncateOwnerReply(text);
    text = dedupeRepeatedLead(text);

    changed = true;
    while (changed) {
      changed = false;
      const next = text.replace(/^\s*[.,;:!?…]+\s*/, "");
      if (next !== text) {
        text = next.trim();
        changed = true;
      }
    }

    return text.replace(/\s+/g, " ").trim();
  }

  function buildReviewPoolFromParts(gender, seedPrefix, limit = 480) {
    const config = GENERIC_REVIEW_PARTS[gender];
    const names = gender === "female" ? FEMALE_REVIEW_NAMES : MALE_REVIEW_NAMES;
    const details = Array.isArray(config.details) && config.details.length ? config.details : config.specifics;
    const result = [];
    let reviewIndex = 0;

    for (let introIndex = 0; introIndex < config.intros.length; introIndex += 1) {
      for (let specificsIndex = 0; specificsIndex < config.specifics.length; specificsIndex += 1) {
        for (let detailIndex = 0; detailIndex < details.length; detailIndex += 1) {
          for (let endingsIndex = 0; endingsIndex < config.endings.length; endingsIndex += 1) {
            const name = names[reviewIndex % names.length];
            const variant = reviewIndex % 4;
            let text = "";

            if (variant === 0) {
              text = [
                sentence(config.intros[introIndex]),
                sentence(config.specifics[specificsIndex]),
                sentence(details[detailIndex]),
                sentence(config.endings[endingsIndex]),
              ].join(" ");
            } else if (variant === 1) {
              text = [
                sentence(config.intros[introIndex]),
                sentence(details[detailIndex]),
                sentence(config.specifics[specificsIndex]),
                sentence(config.endings[endingsIndex]),
              ].join(" ");
            } else if (variant === 2) {
              text = [
                sentence(config.specifics[specificsIndex]),
                sentence(config.intros[introIndex]),
                sentence(details[detailIndex]),
                sentence(config.endings[endingsIndex]),
              ].join(" ");
            } else {
              text = [
                sentence(config.intros[introIndex]),
                sentence(details[detailIndex]),
                sentence(config.endings[endingsIndex]),
              ].join(" ");
            }

            result.push({
              id: `${seedPrefix}-${gender}-${reviewIndex + 1}`,
              name,
              text,
              gender,
              kind: "generic",
              meta: {
                introKey: `${gender}-intro-${introIndex}`,
                specificsKey: `${gender}-specifics-${specificsIndex}`,
                detailKey: `${gender}-detail-${detailIndex}`,
                endingKey: `${gender}-ending-${endingsIndex}`,
                variantKey: `${gender}-variant-${variant}`,
              },
            });

            reviewIndex += 1;
            if (result.length >= limit) return result;
          }
        }
      }
    }

    return result;
  }

  const GENERIC_REVIEW_POOL = [
    ...buildReviewPoolFromParts("female", "generic", 720),
    ...buildReviewPoolFromParts("male", "generic", 720),
  ];

  function getReviewSlotCount(scroller, fallback) {
    const existing = scroller ? scroller.querySelectorAll(".review-item").length : 0;
    return Math.max(existing || fallback, 1);
  }

  function renderReviewItems(scroller, reviews) {
    if (!scroller) return;
    const fragment = document.createDocumentFragment();
    reviews.forEach((review) => {
      const item = document.createElement("div");
      item.className = "review-item";

      const head = document.createElement("p");
      head.className = "review-head";
      head.textContent = String(review.name || "").toUpperCase();

      const text = document.createElement("p");
      text.className = "review-text";
      text.textContent = review.text || "";

      item.append(head, text);
      fragment.appendChild(item);
    });
    scroller.replaceChildren(fragment);
  }

  function createObjectReviewCard(review) {
    const card = document.createElement("article");
    card.className = "review-card";

    const top = document.createElement("div");
    top.className = "review-card__top";

    const author = document.createElement("strong");
    author.textContent = String(review.name || "Гость").toUpperCase();

    const kind = document.createElement("span");
    kind.textContent = "Гость";

    const text = document.createElement("p");
    text.textContent = review.text || "";

    top.append(author, kind);
    card.append(top, text);
    return card;
  }

  function getObjectReviewSlotCount(panel) {
    const existing = panel ? panel.querySelectorAll(".review-card").length : 0;
    return Math.max(existing || 2, 1);
  }

  function renderObjectReviewPanels(context, objectPool) {
    const panels = Array.from(document.querySelectorAll(".reviews-panel"));
    if (!panels.length || !objectPool.length) return false;
    let hydrated = false;

    panels.forEach((panel, index) => {
      const grid = panel.querySelector(".reviews-grid");
      if (!grid) return;

      const count = getObjectReviewSlotCount(panel);
      const reviews = pickReviews(
        objectPool,
        count,
        `abhaz:reviews:panel:${context.slug || window.location.pathname}:${index}`
      );
      grid.replaceChildren(...reviews.map(createObjectReviewCard));
      hydrated = true;
    });

    return hydrated;
  }

  function reviewLeadKey(review) {
    const lead = String(review?.text || "")
      .split(/[.!?…]/)[0]
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    return lead;
  }

  function isDiverseReviewCandidate(selected, candidate) {
    if (!candidate) return false;
    const candidateLead = reviewLeadKey(candidate);

    return !selected.some((review) => {
      if (candidateLead && reviewLeadKey(review) === candidateLead) return true;
      if (!candidate.meta || !review.meta) return false;
      return (
        candidate.meta.introKey === review.meta.introKey ||
        candidate.meta.specificsKey === review.meta.specificsKey ||
        candidate.meta.detailKey === review.meta.detailKey ||
        candidate.meta.endingKey === review.meta.endingKey
      );
    });
  }

  function pickDiversifiedSubset(source, count) {
    const remaining = shuffleCopy(source);
    const selected = [];
    const genericPool = source.every((review) => review.kind === "generic");
    const hasFemale = source.some((review) => review.gender === "female");
    const hasMale = source.some((review) => review.gender === "male");
    let preferredGender =
      genericPool && hasFemale && hasMale ? (Math.random() < 0.5 ? "female" : "male") : "";

    while (selected.length < count && remaining.length) {
      let candidateIndex = -1;

      for (let index = 0; index < remaining.length; index += 1) {
        const candidate = remaining[index];
        if (preferredGender && candidate.gender !== preferredGender) continue;
        if (isDiverseReviewCandidate(selected, candidate)) {
          candidateIndex = index;
          break;
        }
      }

      if (candidateIndex === -1 && preferredGender) {
        for (let index = 0; index < remaining.length; index += 1) {
          const candidate = remaining[index];
          if (candidate.gender === preferredGender) {
            candidateIndex = index;
            break;
          }
        }
      }

      if (candidateIndex === -1) {
        candidateIndex = remaining.findIndex((candidate) => isDiverseReviewCandidate(selected, candidate));
      }

      if (candidateIndex === -1) {
        candidateIndex = 0;
      }

      const [picked] = remaining.splice(candidateIndex, 1);
      if (picked) {
        selected.push(picked);
        if (preferredGender) {
          preferredGender = preferredGender === "female" ? "male" : "female";
        }
      }
    }

    return selected;
  }

  function pickReviews(pool, count, storageKey) {
    const source = Array.isArray(pool) ? pool.filter((review) => review && review.text) : [];
    if (!source.length) return [];

    const actualCount = Math.max(1, Math.min(count || 1, source.length));
    let previousIds = [];

    try {
      previousIds = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
    } catch (error) {
      previousIds = [];
    }

    let selected = [];
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const candidate = pickDiversifiedSubset(source, actualCount);
      const candidateIds = candidate.map((review) => review.id);
      if (!previousIds.length || candidateIds.join("|") !== previousIds.join("|")) {
        selected = candidate;
        break;
      }
      selected = candidate;
    }

    try {
      sessionStorage.setItem(storageKey, JSON.stringify(selected.map((review) => review.id)));
    } catch (error) {
      /* ignore */
    }

    return selected;
  }

  function normalizeBankReview(entry, fallbackId, fallbackObjectSlug = "") {
    if (!entry || typeof entry !== "object") return null;
    const text = sentence(cleanReviewTextForDisplay(entry.text || ""));
    if (!text) return null;
    const gender = entry.gender === "male" ? "male" : "female";
    const names = gender === "male" ? MALE_REVIEW_NAMES : FEMALE_REVIEW_NAMES;
    const name = sanitizeReviewName(entry.name || "", text) || names[stableIndex(text, names.length)];
    return {
      id: String(entry.id || fallbackId || `ocr-${stableIndex(text, 10_000_000)}`),
      name,
      gender,
      text,
      kind: "ocr",
      object_slug: entry.object_slug || fallbackObjectSlug || "",
      source_image: entry.source_image || "",
      source: "ocr_screenshots",
    };
  }

  function sanitizeBankPayload(payload) {
    const global = [];
    const byObject = {};
    const globalSource = Array.isArray(payload?.global) ? payload.global : [];

    globalSource.forEach((entry, index) => {
      const normalized = normalizeBankReview(entry, `ocr-global-${index + 1}`);
      if (normalized) global.push(normalized);
    });

    const byObjectSource = payload?.by_object && typeof payload.by_object === "object" ? payload.by_object : {};
    Object.entries(byObjectSource).forEach(([slug, entries]) => {
      if (!Array.isArray(entries)) return;
      const cleanSlug = String(slug || "").trim();
      if (!cleanSlug) return;
      const list = entries
        .map((entry, index) => normalizeBankReview(entry, `ocr-${cleanSlug}-${index + 1}`, cleanSlug))
        .filter(Boolean);
      if (list.length) byObject[cleanSlug] = list;
    });

    return {
      global,
      by_object: byObject,
      excluded_fuzzy_slugs: Array.isArray(payload?.excluded_fuzzy_slugs) ? payload.excluded_fuzzy_slugs : [],
    };
  }

  function normalizeSlugForMatch(value) {
    return String(value || "")
      .toLowerCase()
      .trim()
      .replace(/^\/+|\/+$/g, "")
      .replace(/-+/g, "-")
      .replace(/-\d{3,6}$/g, "");
  }

  function slugMatchScore(sourceSlug, targetSlug) {
    if (!sourceSlug || !targetSlug) return 0;
    if (sourceSlug === targetSlug) return 10_000 + sourceSlug.length;
    if (sourceSlug.startsWith(targetSlug)) return 5_000 + targetSlug.length;
    if (targetSlug.startsWith(sourceSlug)) return 4_000 + sourceSlug.length;

    const sourceTokens = sourceSlug.split("-").filter(Boolean);
    const targetTokens = targetSlug.split("-").filter(Boolean);
    const sourceSet = new Set(sourceTokens);
    const common = targetTokens.filter((token) => sourceSet.has(token));
    if (!common.length) return 0;
    const ratio = common.length / Math.max(sourceTokens.length, targetTokens.length);
    return Math.round(ratio * 1000) + common.length;
  }

  function reviewObjectBankUrl(slug) {
    return `${CDN_MEDIA_BASE}/reviews/${encodeURIComponent(slug)}/bank.json?v=${ASSET_VERSION}`;
  }

  function fetchReviewBankJson(url, options = {}) {
    return fetch(url).then((response) => {
      if (options.optional && response.status === 404) return null;
      if (!response.ok) {
        throw new Error(`Не удалось загрузить ${url}: ${response.status}`);
      }
      return response.json();
    });
  }

  function sanitizeSplitBankPayload(globalPayload, objectPayload, slug) {
    const globalBank = sanitizeBankPayload({
      global: Array.isArray(globalPayload?.global) ? globalPayload.global : [],
      excluded_fuzzy_slugs: Array.isArray(globalPayload?.excluded_fuzzy_slugs)
        ? globalPayload.excluded_fuzzy_slugs
        : [],
    });
    const byObject = {};
    const objectSlug = String(objectPayload?.slug || slug || "").trim();
    const objectEntries = Array.isArray(objectPayload?.reviews) ? objectPayload.reviews : [];
    const objectReviews = objectEntries
      .map((entry, index) => normalizeBankReview(entry, `ocr-${objectSlug || slug}-${index + 1}`, objectSlug || slug))
      .filter(Boolean);

    if (objectReviews.length) {
      if (slug) byObject[slug] = objectReviews;
      if (objectSlug && objectSlug !== slug) byObject[objectSlug] = objectReviews;
    }

    return {
      global: globalBank.global,
      by_object: byObject,
      excluded_fuzzy_slugs: globalBank.excluded_fuzzy_slugs,
    };
  }

  async function loadScreenshotReviewBank() {
    if (screenshotReviewBank) return screenshotReviewBank;
    if (screenshotReviewBankPromise) return screenshotReviewBankPromise;

    const slug = isObjectPage() ? extractObjectSlugFromPathname() : "";
    const globalPromise = fetchReviewBankJson(SCREENSHOT_REVIEW_GLOBAL_URL);
    const objectPromise = slug
      ? fetchReviewBankJson(reviewObjectBankUrl(slug), { optional: true }).catch((error) => {
          console.warn("Не удалось загрузить OCR-отзывы объекта", slug, error);
          return null;
        })
      : Promise.resolve(null);

    screenshotReviewBankPromise = Promise.all([globalPromise, objectPromise])
      .then(([globalPayload, objectPayload]) => {
        screenshotReviewBank = sanitizeSplitBankPayload(globalPayload, objectPayload, slug);
        return screenshotReviewBank;
      })
      .catch((error) => {
        console.error("Не удалось загрузить OCR-базу отзывов", error);
        screenshotReviewBank = { global: [], by_object: {} };
        return screenshotReviewBank;
      })
      .finally(() => {
        screenshotReviewBankPromise = null;
      });

    return screenshotReviewBankPromise;
  }

  function getGlobalReviewPool() {
    const fromScreenshots = screenshotReviewBank?.global || [];
    return fromScreenshots;
  }

  function getExcludedFuzzyReviewSlugs() {
    const fromBank = screenshotReviewBank?.excluded_fuzzy_slugs;
    return Array.isArray(fromBank) ? new Set(fromBank) : new Set();
  }

  function getObjectReviewPool(slug) {
    const cleanSlug = String(slug || "").trim();
    if (!cleanSlug) return [];
    const byObject = screenshotReviewBank?.by_object || {};
    if (Array.isArray(byObject[cleanSlug])) return byObject[cleanSlug];

    const normalizedTarget = normalizeSlugForMatch(cleanSlug);
    if (!normalizedTarget) return [];

    const excluded = getExcludedFuzzyReviewSlugs();
    let bestKey = "";
    let bestScore = 0;

    Object.keys(byObject).forEach((candidateKey) => {
      if (excluded.has(candidateKey)) return;
      const candidateNorm = normalizeSlugForMatch(candidateKey);
      const score = slugMatchScore(candidateNorm, normalizedTarget);
      if (score > bestScore) {
        bestScore = score;
        bestKey = candidateKey;
      }
    });

    if (!bestKey || bestScore < 1200) return [];
    return Array.isArray(byObject[bestKey]) ? byObject[bestKey] : [];
  }

  function detectReviewGender(text) {
    const lower = String(text || "").toLowerCase();
    const femaleMarkers = [
      "ехала",
      "переживала",
      "сомневалась",
      "выбирала",
      "боялась",
      "рада",
      "благодарна",
      "ценю",
      "искала",
      "хотела",
    ];
    const maleMarkers = [
      "ехал",
      "переживал",
      "сомневался",
      "выбирал",
      "опасался",
      "рад",
      "благодарен",
      "искал",
      "хотелось",
      "понравилось",
    ];
    const femaleHits = femaleMarkers.reduce((sum, marker) => sum + (lower.includes(marker) ? 1 : 0), 0);
    const maleHits = maleMarkers.reduce((sum, marker) => sum + (lower.includes(marker) ? 1 : 0), 0);
    return femaleHits > maleHits ? "female" : "male";
  }

  function pickFantasyReviewName(gender, seedSource) {
    const names = gender === "female" ? FEMALE_REVIEW_NAMES : MALE_REVIEW_NAMES;
    return names[hashString(seedSource || names.join("|")) % names.length];
  }

  function sanitizeReviewName(rawName, reviewText) {
    const cleaned = String(rawName || "")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const first = cleaned.split(/[\s,.;:!?()[\]{}"«»]+/).find((part) => /^[А-Яа-яЁё-]+$/.test(part || ""));
    if (first) {
      const normalized = first.toLowerCase();
      return normalized.charAt(0).toUpperCase() + normalized.slice(1);
    }
    return pickFantasyReviewName(detectReviewGender(reviewText), reviewText);
  }

  function extractObjectSlugFromPathname() {
    const match = window.location.pathname.match(/^\/(?:hotels|kvartira)\/([^/]+)\/?$/);
    return match ? match[1] : "";
  }

  function ensureEmojiLine(value, emoji) {
    const text = String(value || "").replace(/<br\s*\/?>/gi, " ").replace(/\s+/g, " ").trim();
    if (!text) return "";
    if (/^[📍🏖🏝]/.test(text)) return text;
    return `${emoji} ${text}`;
  }

  function extractHotelSummaryLines(row) {
    const source = [row?.summary, row?.excerpt, row?.details?.lead]
      .filter(Boolean)
      .join("\n")
      .replace(/<br\s*\/?>/gi, "\n");

    let location = ensureEmojiLine(row?.location_text, "📍");
    let beach = ensureEmojiLine(row?.beach_text, "🏖");
    if (location && beach) return { location, beach };

    const lines = source
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    for (const line of lines) {
      const lower = line.toLowerCase();
      if (!location && (line.includes("📍") || lower.includes("ул.") || lower.includes("улиц") || lower.includes("пос."))) {
        location = ensureEmojiLine(line.replace("📍", "").trim(), "📍");
        continue;
      }
      if (!beach && (line.includes("🏖") || line.includes("🏝") || lower.includes("пляж") || lower.includes("мор"))) {
        beach = ensureEmojiLine(line.replace("🏖", "").replace("🏝", "").trim(), "🏖");
      }
    }

    if (!location) {
      const filters = row?.details?.filters || {};
      const city = CITY_LABELS[firstValue(filters.city)] || extractCityFromSummary(source) || "Абхазия";
      location = ensureEmojiLine(city, "📍");
    }
    if (!beach) {
      const filters = row?.details?.filters || {};
      const distance = DISTANCE_BY_FILTER[firstValue(filters.distance)] || extractDistanceFromSummary(source) || "до пляжа";
      beach = ensureEmojiLine(distance, "🏖");
    }

    return { location, beach };
  }

  function extractObjectReviewContext(row) {
    const slug = row?.slug || extractObjectSlugFromPathname();
    const title =
      row?.title ||
      document.querySelector(".hotel-hero-v2 h1")?.textContent?.trim() ||
      document.querySelector(".hotel-site-concept__intro h1")?.textContent?.trim() ||
      document.querySelector("h1")?.textContent?.trim() ||
      "";
    const summarySource = [
      row?.summary,
      row?.excerpt,
      row?.details?.lead,
      document.querySelector(".hotel-hero-v2 .lead")?.textContent,
      document.querySelector(".hotel-card__description")?.textContent,
      document.querySelector(".location")?.textContent,
    ]
      .filter(Boolean)
      .join(" ");
    const summaryLines = row ? extractHotelSummaryLines(row) : { location: "", beach: "" };
    const locationText = cleanReviewFact(
      row?.location_text ||
        summaryLines.location ||
        document.querySelector(".hotel-card__rating strong")?.textContent ||
        ""
    );
    const beachText = cleanReviewFact(row?.beach_text || summaryLines.beach || "");
    const distanceText = cleanReviewFact(extractDistanceFromSummary(summarySource));
    const capacityText = cleanReviewFact(row?.capacity_text || extractCapacityFromSummary(summarySource));

    return {
      slug,
      title,
      locationText,
      beachText,
      distanceText,
      capacityText,
    };
  }

  function isObjectPage() {
    return /^\/(?:hotels|kvartira)\/[^/]+\/?$/.test(window.location.pathname);
  }

  function renderGenericReviews() {
    /* Не трогаем блоки с ручными отзывами из /data/guest-reviews.json (data-random-reviews). */
    const scrollers = Array.from(
      document.querySelectorAll(".reviews-scroller:not([data-random-reviews])")
    );
    const genericPool = getGlobalReviewPool();
    if (!genericPool.length) return;
    scrollers.forEach((scroller, index) => {
      const count = getReviewSlotCount(scroller, window.location.pathname === "/" ? 8 : 4);
      const reviews = pickReviews(
        genericPool,
        count,
        `abhaz:reviews:generic:${window.location.pathname}:${index}`
      );
      renderReviewItems(scroller, reviews);
    });
  }

  function renderHotelReviews(row) {
    const context = extractObjectReviewContext(row);
    const objectPool = getObjectReviewPool(context.slug);
    renderObjectReviewPanels(context, objectPool);
    const scrollers = Array.from(
      document.querySelectorAll(".reviews-scroller:not([data-random-reviews])")
    );
    if (!scrollers.length) return;

    const pool = objectPool.length ? objectPool : getGlobalReviewPool();
    if (!pool.length) return;

    scrollers.forEach((scroller, index) => {
      const count = getReviewSlotCount(scroller, 4);
      const reviews = pickReviews(
        pool,
        count,
        `abhaz:reviews:object:${context.slug || window.location.pathname}:${index}:${objectPool.length ? "specific" : "fallback"}`
      );
      renderReviewItems(scroller, reviews);
    });
  }

  function renderReviewsForCurrentPage() {
    if (isObjectPage()) {
      renderHotelReviews();
    } else {
      renderGenericReviews();
    }
  }

  /**
   * Якоря (#guide, #contacts…) на длинных страницах: ленивый контент выше
   * цели доезжает после перехода, и блок уплывает. Доводим скролл до цели,
   * пока вёрстка не стабилизируется; ручной скролл пользователя — стоп.
   */
  function initStableAnchorScroll() {
    let cancelCurrent = null;

    function settleScrollTo(target) {
      if (typeof cancelCurrent === "function") cancelCurrent();
      let cancelled = false;
      const stop = () => {
        cancelled = true;
      };
      ["wheel", "touchstart", "keydown"].forEach((eventName) =>
        window.addEventListener(eventName, stop, { once: true, passive: true })
      );
      cancelCurrent = stop;

      const align = (smooth) => {
        target.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
      };
      align(true);
      let lastTop = null;
      let settledTicks = 0;
      const started = Date.now();
      const timer = window.setInterval(() => {
        if (cancelled || Date.now() - started > 2600) {
          window.clearInterval(timer);
          return;
        }
        const top = Math.round(target.getBoundingClientRect().top);
        if (lastTop !== null && Math.abs(top - lastTop) <= 2) {
          settledTicks += 1;
          if (Math.abs(top) > 4) align(false);
          if (settledTicks >= 3 && Math.abs(top) <= 4) {
            window.clearInterval(timer);
            return;
          }
        } else {
          settledTicks = 0;
          if (lastTop !== null) align(false);
        }
        lastTop = Math.round(target.getBoundingClientRect().top);
      }, 220);
    }

    document.addEventListener("click", (event) => {
      const link = event.target.closest('a[href^="#"]');
      if (!link) return;
      const id = decodeURIComponent(link.getAttribute("href").slice(1));
      if (!id) return;
      const target = document.getElementById(id);
      if (!target) return;
      event.preventDefault();
      if (typeof history.pushState === "function") {
        history.pushState(null, "", `#${id}`);
      }
      settleScrollTo(target);
    });

    if (window.location.hash) {
      const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      if (target) {
        window.setTimeout(() => settleScrollTo(target), 150);
      }
    }
  }

  function getScreenshotReviewTargets() {
    return Array.from(
      document.querySelectorAll(".reviews-panel, .reviews-scroller:not([data-random-reviews])")
    );
  }

  function initLazyScreenshotReviews() {
    const targets = getScreenshotReviewTargets();
    if (!targets.length) return;

    let started = false;
    const hydrate = () => {
      if (started) return;
      started = true;
      loadScreenshotReviewBank().then(() => {
        renderReviewsForCurrentPage();
      });
    };

    if (!("IntersectionObserver" in window)) {
      setTimeout(hydrate, 1200);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        hydrate();
      },
      { rootMargin: "600px 0px" }
    );

    targets.forEach((target) => observer.observe(target));
  }

  function normalizeIndexListing(row) {
    if (!row || typeof row !== "object") return row;
    const listing = { ...row };
    const details = listing.details && typeof listing.details === "object" ? listing.details : {};
    listing.details = {
      ...details,
      filters: details.filters && typeof details.filters === "object" ? details.filters : {},
    };
    if (typeof listing.has_video !== "boolean") {
      listing.has_video = Boolean(listing.has_video);
    }
    return listing;
  }

  async function loadCatalogIndex() {
    if (!catalogIndexPromise) {
      catalogIndexPromise = fetch(CATALOG_INDEX_URL, { credentials: "same-origin" })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`catalog index HTTP ${response.status}`);
          }
          return response.json();
        })
        .then((payload) => {
          const rows = Array.isArray(payload?.listings) ? payload.listings : [];
          return rows.map(normalizeIndexListing);
        })
        .catch((error) => {
          catalogIndexPromise = null;
          throw error;
        });
    }
    return catalogIndexPromise;
  }

  async function fetchListings(options = {}) {
    const rows = await loadCatalogIndex();
    let filtered = rows.filter((row) => row?.is_active !== false);
    if (options.sourceKind) {
      filtered = filtered.filter((row) => row.source_kind === options.sourceKind);
    }
    if (options.slug) {
      filtered = filtered.filter((row) => row.slug === options.slug);
    }
    filtered.sort((left, right) => {
      const leftDate = String(left?.published_at || "");
      const rightDate = String(right?.published_at || "");
      if (leftDate !== rightDate) return rightDate.localeCompare(leftDate);
      return Number(right?.id || 0) - Number(left?.id || 0);
    });
    if (options.slug) return filtered.slice(0, 1);
    return filtered;
  }

  async function fetchListingBySlug(slug) {
    const rows = await fetchListings({ slug });
    return rows[0] || null;
  }

  function localCardFallback(row) {
    if (!row?.slug) return "";
    const folder = row.source_kind === "kvartira" ? "kvartira-cards" : "cards";
    return toCdnMediaUrl(`/media/${folder}/${row.slug}.jpg`);
  }

  function toCdnMediaUrl(value) {
    const n = normalizeMediaUrl(value);
    if (!n) return "";
    if (n.startsWith(CDN_MEDIA_BASE)) return n;

    const yandexFolders = /^(cards|hotels|kvartira|kvartira-cards|branding|blog|reviews)\//;
    let rel = "";

    if (n.includes("/media/")) {
      rel = n.slice(n.indexOf("/media/") + "/media/".length).split("?")[0].replace(/^\/+/, "");
    } else if (!/^https?:\/\//i.test(n)) {
      rel = n.replace(/^(\.\.\/)+/, "").replace(/^\/+/, "").replace(/^media\//, "");
    }

    if (rel) {
      try {
        rel = decodeURIComponent(rel);
      } catch (error) {
        /* keep raw rel */
      }
      if (yandexFolders.test(rel)) {
        return `${CDN_MEDIA_BASE}/${rel.split("/").map(encodeURIComponent).join("/")}`;
      }
      if (rel.startsWith("videos/")) {
        return `${CDN_MEDIA_BASE}/${rel.split("/").map(encodeURIComponent).join("/")}`;
      }
    }

    return n;
  }

  /** Turn local media image paths into Yandex Object Storage URLs. */
  function absolutizeKvartiraCoverUrl(url) {
    const n = normalizeMediaUrl(url);
    if (!n) return "";
    return toCdnMediaUrl(n);
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

    return raw;
  }

  function pickLocalVideoFallbackPoster(video) {
    const grid = video.closest(".media-grid, .hotel-card__gallery, .hotel-media-section");
    const img = grid?.querySelector("img[src]:not(.local-video-preview)");
    if (!img) return "";
    return gallerySrcFromImage(img);
  }

  function applyLocalVideoPoster(video, posterUrl, kind) {
    if (!video || !posterUrl) return;
    if (video.dataset.posterReady === "frame") return;
    video.poster = posterUrl;
    video.dataset.posterReady = kind || "fallback";
  }

  function captureVideoFrameToPoster(targetVideo, probeVideo) {
    const width = probeVideo.videoWidth;
    const height = probeVideo.videoHeight;
    if (!width || !height) return false;

    try {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      canvas.getContext("2d").drawImage(probeVideo, 0, 0, width, height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.86);
      if (dataUrl && dataUrl.length > 1200) {
        targetVideo.poster = dataUrl;
        targetVideo.dataset.posterReady = "frame";
        return true;
      }
    } catch (error) {
      /* tainted canvas (CORS) */
    }

    return false;
  }

  function wireLocalVideoPoster(video) {
    if (!video || !video.classList.contains("local-video")) return;
    if (video.dataset.posterWired === "1" || video.dataset.posterReady === "frame") return;

    video.dataset.posterWired = "1";
    applyLocalVideoPoster(video, pickLocalVideoFallbackPoster(video), "fallback");
  }

  function initLocalVideoPosters(root = document) {
    if (!root?.querySelectorAll) return;
    root.querySelectorAll("video.local-video").forEach(wireLocalVideoPoster);
  }

  /**
   * Плитка видео обрезана под фото (object-fit: cover), поэтому вертикальные
   * ролики до старта выглядят горизонтальными. После нажатия «плей» снимаем
   * кадрирование, и видео играет в своих настоящих пропорциях.
   * Событие play не всплывает — ловим его на фазе перехвата.
   */
  function initLocalVideoNaturalPlayback() {
    document.addEventListener(
      "play",
      (event) => {
        const video = event.target;
        if (!(video instanceof HTMLVideoElement)) return;
        if (!video.classList.contains("local-video")) return;
        video.classList.add("is-playing");
      },
      true
    );
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
    /* Главное фото страницы объекта — то же, что в карточке на сайте (галерея photo-01…). */
    if (row.slug) {
      push(`https://storage.yandexcloud.net/abhazbereg-media/media/kvartira/${row.slug}/photo-01.jpg`);
      push(`https://storage.yandexcloud.net/abhazbereg-media/media/kvartira/${row.slug}/photo-02.jpg`);
    }
    push(card?.public_url);
    push(image?.public_url);
    push(row.cover_url);
    if (row.slug) {
      push(`https://storage.yandexcloud.net/abhazbereg-media/media/kvartira-cards/${row.slug}-cover.jpg`);
      push(`https://storage.yandexcloud.net/abhazbereg-media/media/kvartira-cards/${row.slug}.jpg`);
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

  function toFilterArray(value) {
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
    if (typeof value === "string") {
      const raw = value.trim();
      if (!raw) return [];
      const chunks = raw.split("|").map((item) => item.trim());
      const nonEmpty = chunks.filter(Boolean);
      // Recover malformed values like "b|e|a|c|h|f|r|o|n|t|||o|v|e|r|-|1|0".
      if (nonEmpty.length >= 4 && nonEmpty.every((item) => item.length === 1)) {
        if (raw.includes("|||")) {
          return raw
            .split("|||")
            .map((part) => part.split("|").join("").trim())
            .filter(Boolean);
        }
        const merged = raw.split("|").join("").trim();
        return merged ? [merged] : [];
      }
      return nonEmpty;
    }
    if (typeof value === "number") return [String(value)];
    return [];
  }

  function dedupe(values) {
    return Array.from(new Set(values.filter(Boolean)));
  }

  function normalizePriceValue(value) {
    const raw = String(value || "").trim();
    const lower = raw.toLowerCase();
    if (!raw) return "";
    if (lower.includes("эконом")) return "economy";
    if (lower.includes("премиум")) return "premium";
    if (lower.includes("10000") || lower.includes("10 000")) return "midrange";
    if (lower.includes("5000") || lower.includes("5 000")) return "economy";
    if (lower.includes("до 5000")) return "economy";
    if (lower.includes("до 10000")) return "midrange";
    if (raw === "economy" || raw === "midrange" || raw === "premium") return raw;
    const upTo = raw.match(/^up-to-(\d{3,5})$/);
    if (upTo) {
      const price = Number(upTo[1]);
      if (price <= 5000) return "economy";
      if (price <= 10000) return "midrange";
      return "premium";
    }
    return raw;
  }

  function normalizeBeachValue(value, cityValues) {
    const raw = String(value || "").trim();
    const lower = raw.toLowerCase();
    if (!raw) return "";
    const cities = new Set((cityValues || []).map((item) => String(item || "").trim()));
    const isSukhum = cities.has("sukhum");
    const isLdzaaOrPitsunda = cities.has("ldzaa") || cities.has("pitsunda");

    if (raw === BEACH_FILTERS.SAND_LDZAA || raw === BEACH_FILTERS.SAND_SUKHUM || raw === BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA || raw === BEACH_FILTERS.PITSUNDA_BAY_MIXED || raw === BEACH_FILTERS.PEBBLE) {
      return raw;
    }
    if (raw === "sand") return isSukhum ? BEACH_FILTERS.SAND_SUKHUM : BEACH_FILTERS.SAND_LDZAA;
    if (raw === "pine-pebble") return BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA;
    if (raw === "mixed") return isLdzaaOrPitsunda ? BEACH_FILTERS.PITSUNDA_BAY_MIXED : BEACH_FILTERS.PEBBLE;
    if (lower.includes("песчан") && lower.includes("сухум")) return BEACH_FILTERS.SAND_SUKHUM;
    if (lower.includes("песчан") && lower.includes("лдзаа")) return BEACH_FILTERS.SAND_LDZAA;
    if (lower.includes("соснов") && lower.includes("лдзаа")) return BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA;
    if (lower.includes("соснов") && lower.includes("пицунд")) return BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA;
    if (lower.includes("пицундск") && lower.includes("бухт")) return BEACH_FILTERS.PITSUNDA_BAY_MIXED;
    if (lower.includes("галеч")) return BEACH_FILTERS.PEBBLE;
    if (lower.includes("песчан")) return isSukhum ? BEACH_FILTERS.SAND_SUKHUM : BEACH_FILTERS.SAND_LDZAA;
    return raw;
  }

  function normalizeRoomValue(value) {
    const raw = String(value || "").trim();
    const lower = raw.toLowerCase();
    if (!raw || raw === "ac" || raw === "one-room") return "";
    if (raw === "two-room") return "two-room-plus";
    if (raw === "beachfront-room") return "beachfront-room";
    if (lower.includes("вид на море")) return "sea-view";
    if (
      lower.includes("прямо на берегу") ||
      lower.includes("на первой линии") ||
      lower.includes("отели на берегу") ||
      lower.includes("на берегу моря")
    ) {
      return "beachfront-room";
    }
    if (lower.includes("бассейн")) return "pool";
    if (lower.includes("балкон")) return "balcony";
    if (lower.includes("террас")) return "terrace";
    if (lower.includes("кухн")) return "kitchen";
    if (lower.includes("пять") && lower.includes("гостей")) return "five-plus";
    if (lower.includes("две комнат")) return "two-room-plus";
    return raw;
  }

  function normalizeStayValue(value) {
    const raw = String(value || "").trim();
    const lower = raw.toLowerCase();
    if (!raw || raw === "kids") return "";
    if (lower.includes("домики") || lower.includes("коттедж")) return "cottages";
    if (lower.includes("квартир")) return "apartments";
    if (lower.includes("дом под ключ")) return "turnkey-house";
    if (lower.includes("животн")) return "pets";
    if (lower.includes("без маленьких детей")) return "no-small-kids";
    return raw;
  }

  function inferStayByText(row) {
    const blob = `${row?.title || ""} ${row?.summary || ""} ${row?.excerpt || ""} ${row?.details?.lead || ""}`.toLowerCase();
    const values = [];
    if (/(домик|коттедж|шале|бунгало|глэмпинг|glamping)/.test(blob)) values.push("cottages");
    if (/(квартир|апартамент|студи)/.test(blob)) values.push("apartments");
    if (/дом под ключ/.test(blob)) values.push("turnkey-house");
    if (/(с животн|питомц|pet friendly|с собачк)/.test(blob)) values.push("pets");
    return values;
  }

  function inferStayByCard(card) {
    const title = card?.querySelector("h3")?.textContent || "";
    const summary = card?.querySelector("p")?.textContent || "";
    const href = card?.getAttribute("href") || "";
    const blob = `${title} ${summary} ${href}`.toLowerCase();
    const values = [];
    if (/(домик|коттедж|шале|бунгало|глэмпинг|glamping)/.test(blob)) values.push("cottages");
    if (/(квартир|апартамент|студи)/.test(blob)) values.push("apartments");
    if (/дом под ключ/.test(blob)) values.push("turnkey-house");
    if (/(с животн|питомц|pet friendly|с собачк)/.test(blob)) values.push("pets");
    return values;
  }

  function normalizeFiltersForCard(filters, row) {
    const source = filters || {};
    const city = dedupe(toFilterArray(source.city));
    const distance = dedupe(toFilterArray(source.distance));
    const food = dedupe(toFilterArray(source.food));
    const price = dedupe(toFilterArray(source.price).map(normalizePriceValue));
    const beach = dedupe(toFilterArray(source.beach).map((value) => normalizeBeachValue(value, city)));
    const room = dedupe(toFilterArray(source.room).map(normalizeRoomValue));
    const stay = dedupe([...toFilterArray(source.stay).map(normalizeStayValue), ...inferStayByText(row)]);

    return { distance, food, price, city, beach, room, stay };
  }

  function normalizeCardFilterValues(group, values, card) {
    const source = toFilterArray(values);
    if (!source.length) return [];

    if (group === "price") {
      return dedupe(source.map(normalizePriceValue));
    }

    if (group === "beach") {
      const cityValues = toFilterArray(card?.dataset?.filterCity || "");
      if (!cityValues.length) {
        const text = `${card?.querySelector("h3")?.textContent || ""} ${card?.querySelector("p")?.textContent || ""}`.toLowerCase();
        if (text.includes("сухум")) cityValues.push("sukhum");
        if (text.includes("лдзаа")) cityValues.push("ldzaa");
        if (text.includes("пицунда")) cityValues.push("pitsunda");
      }
      return dedupe(source.map((value) => normalizeBeachValue(value, cityValues)));
    }

    if (group === "room") {
      return dedupe(source.map(normalizeRoomValue));
    }

    if (group === "stay") {
      const normalized = dedupe(source.map(normalizeStayValue));
      return dedupe([...normalized, ...inferStayByCard(card)]);
    }

    return source;
  }

  function inferCardFilterValues(group, card) {
    const title = (card?.querySelector("h3")?.textContent || "").toLowerCase();
    const summary = (card?.querySelector("p")?.textContent || "").toLowerCase();
    const href = (card?.getAttribute("href") || "").toLowerCase();
    const blob = `${title} ${summary} ${href}`;

    if (group === "city") {
      const values = [];
      if (blob.includes("сухум")) values.push("sukhum");
      if (blob.includes("новый афон")) values.push("new-afon");
      if (blob.includes("гудаута")) values.push("gudauta");
      if (blob.includes("лдзаа")) values.push("ldzaa");
      if (blob.includes("пицунда")) values.push("pitsunda");
      if (blob.includes("алахадз")) values.push("alakhadzy");
      if (blob.includes("гагра")) values.push("gagra");
      if (blob.includes("цандрипш")) values.push("tsandripsh");
      return dedupe(values);
    }

    if (group === "distance") {
      if (/0\s*(мин|минут)/.test(blob) || /на первой линии|прямо на пляже|на берегу/.test(blob)) {
        return ["beachfront"];
      }
      const minuteMatch = blob.match(/(\d{1,2})\s*(мин|минут)/);
      if (!minuteMatch) return [];
      const value = Number(minuteMatch[1]);
      if (value <= 5) return ["up-to-5"];
      if (value <= 10) return ["up-to-10"];
      return ["over-10"];
    }

    if (group === "beach") {
      const cities = inferCardFilterValues("city", card);
      if (blob.includes("соснов")) return [BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA];
      if (blob.includes("пицунд") && blob.includes("бухт")) return [BEACH_FILTERS.PITSUNDA_BAY_MIXED];
      if (blob.includes("песч")) {
        return [cities.includes("sukhum") ? BEACH_FILTERS.SAND_SUKHUM : BEACH_FILTERS.SAND_LDZAA];
      }
      if (blob.includes("галеч")) return [BEACH_FILTERS.PEBBLE];
      return [];
    }

    if (group === "stay") {
      return dedupe(inferStayByCard(card));
    }

    if (group === "room") {
      const values = [];
      if (blob.includes("вид на море")) values.push("sea-view");
      if (blob.includes("прямо на берегу") || blob.includes("на первой линии")) values.push("beachfront-room");
      if (blob.includes("бассейн")) values.push("pool");
      if (blob.includes("балкон")) values.push("balcony");
      if (blob.includes("террас")) values.push("terrace");
      if (blob.includes("кухн")) values.push("kitchen");
      if (/(пять|5)\s*гост/.test(blob)) values.push("five-plus");
      if (blob.includes("2к") || blob.includes("две комнат")) values.push("two-room-plus");
      return dedupe(values);
    }

    return [];
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

  function isLikelyGarbageCityHint(text) {
    const s = String(text || "").trim().toLowerCase();
    if (s.length < 3 || s.length > 48) return true;
    return /^(для|если|когда|чтобы|этот|это|в\s|на\s)/u.test(s);
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

  /** Название для мини-карточки: без промо-хвостов («скидка…», «акция…»). */
  function cleanCardTitle(title) {
    const text = String(title || "");
    const match = text.match(/скидк|акци/i);
    if (!match) return text;
    const cleaned = text
      .slice(0, match.index)
      .replace(/[\s\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\-–—:,·|]+$/u, "")
      .trim();
    return cleaned || text;
  }

  /** Единый блок фактов мини-карточки: 📍адрес, 🏖пляж, 👥вместимость — как в шапке поста. */
  function formatCardFactLines(row) {
    const source = row?.summary || row?.excerpt || row?.details?.lead || "";
    const filters = row?.details?.filters || {};
    const lines = [];
    const location = String(row?.location_text || "").replace(/^[\s\u{FE0F}]+/u, "").trim();
    if (location) {
      lines.push(location.startsWith("📍") ? location : `📍${location}`);
    } else {
      const city = extractCityFromSummary(source) || CITY_LABELS[firstValue(filters.city)];
      if (city) lines.push(`📍${city}`);
    }
    const beach = String(row?.beach_text || "").replace(/^[\s\u{FE0F}]+/u, "").trim();
    if (beach) {
      lines.push(beach.startsWith("🏖") ? beach : `🏖 ${beach}`);
    } else {
      const distance = extractDistanceFromSummary(source) || DISTANCE_BY_FILTER[firstValue(filters.distance)];
      if (distance) lines.push(`🏖 ${distance}`);
    }
    const capacity = extractCapacityFromSummary(source);
    if (capacity) lines.push(`👥 ${capacity}`);
    return lines.join("\n");
  }

  function appendCardFacts(card, row) {
    const desc = document.createElement("p");
    const facts = formatCardFactLines(row);
    if (facts) {
      desc.className = "catalog-card__facts";
      replaceWithLines(desc, facts);
    } else {
      desc.textContent =
        row?.source_kind === "kvartira" ? formatKvartiraCardSummary(row) : formatHotelCardSummary(row);
    }
    card.appendChild(desc);
  }

  /** Короткие строки 📍 / 🏖 как у карточек отелей на главной (не абзацы из excerpt). */
  function extractKvartiraPinLine(text) {
    const t = String(text || "").trim();
    if (!t.includes("📍")) return "";
    const idx = t.indexOf("📍");
    let slice = t.slice(idx);
    const beachIdx = slice.search(/🏖️|🏖|🏝️|🏝/u);
    if (beachIdx !== -1) slice = slice.slice(0, beachIdx).trim();
    slice = slice.replace(/\s+/g, " ").trim();
    if (slice.length > 130) slice = `${slice.slice(0, 127).trim()}…`;
    return slice;
  }

  function extractKvartiraBeachLine(text, filters) {
    const t = String(text || "").trim();
    const idx = t.search(/🏖️|🏖|🏝️|🏝/u);
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

  /** Текст для первой строки плашки: без блока «до пляжа» и без 📍 — только про жильё. */
  function stripKvartiraSummaryToProse(raw) {
    const t = String(raw || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    const labeled = t.match(/✔️[^:]+\:\s*(.+)$/i);
    if (labeled) return labeled[1].trim();
    let rest = t;
    const pin = extractKvartiraPinLine(rest);
    if (pin) rest = rest.replace(pin, " ").replace(/\s+/g, " ").trim();
    rest = rest.replace(/^(?:🏖️|🏖|🏝️|🏝)\s*.{3,160}?(\.|$)\s*/u, "").trim();
    rest = rest.replace(/^\d+\s*[-–]?\s*\d*\s*мин[^\n.]{0,100}\.\s*/i, "").trim();
    rest = rest.replace(/^[^\p{L}\d]*\d+\s*[-–]?\s*\d*\s*мин[^\n.]{0,100}\.\s*/u, "").trim();
    return rest.replace(/^✔️[^:]*:\s*/i, "").trim();
  }

  function normalizeKvartiraPinLine(row) {
    const source = row?.summary || row?.excerpt || row?.details?.lead || "";
    const filters = row?.details?.filters || {};
    const extracted = extractKvartiraPinLine(source);
    if (extracted) {
      let inner = extracted.replace(/^📍\s*/, "").trim();
      if (!inner.endsWith(".")) inner += ".";
      return `📍 ${inner}`;
    }
    const fromFilter = CITY_LABELS[firstValue(filters.city)];
    const fromLeadRaw = source.length < 160 ? extractCityFromSummary(source) : "";
    const fromLead = isLikelyGarbageCityHint(fromLeadRaw) ? "" : fromLeadRaw;
    const city = fromFilter || fromLead || "";
    if (city) return `📍 ${city.replace(/\s+/g, " ").trim()}.`;
    return "📍 Абхазия.";
  }

  function normalizeKvartiraBeachLine(row) {
    const source = row?.summary || row?.excerpt || row?.details?.lead || "";
    const filters = row?.details?.filters || {};
    let raw = extractKvartiraBeachLine(source, filters);
    if (raw) {
      raw = raw.replace(/^(🏖️|🏖|🏝️|🏝)\s*/u, "").trim();
      return raw ? `🏖 ${raw}` : "";
    }
    const dist = extractDistanceFromSummary(source);
    if (dist) return `🏖 ${dist}`;
    const fb = DISTANCE_BY_FILTER[firstValue(filters.distance)];
    if (fb) return `🏖 ${fb}`;
    return "🏖 Как добраться до пляжа — в карточке объекта.";
  }

  /** Единый образец: короткий тизер (если есть) + 📍 город + 🏖 до пляжа. */
  function formatKvartiraCardSummary(row) {
    const source = row?.summary || row?.excerpt || row?.details?.lead || "";
    const teaser = clampKvartiraCardDescription(stripKvartiraSummaryToProse(source));
    const pin = normalizeKvartiraPinLine(row);
    const beach = normalizeKvartiraBeachLine(row);
    const lines = [];
    if (teaser) lines.push(teaser);
    lines.push(pin, beach);
    return lines.join("\n");
  }

  function renderHotelCards(rows, grid) {
    const fragment = document.createDocumentFragment();

    rows.forEach((row) => {
      const card = document.createElement("a");
      card.className = "catalog-card";
      card.href = pathnameFromUrl(row.page_url, `/hotels/${row.slug}/`);
      if (row.has_video) card.dataset.hasVideo = "1";
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
      appendCatalogMapPlaque(card, primaryCityKeyFromFilters(row.details?.filters));

      card.appendChild(createTextNode("h3", cleanCardTitle(row.title)));
      appendCardFacts(card, row);
      fragment.appendChild(card);
    });

    grid.replaceChildren(fragment);
    initLocalVideoPosters(grid);
    initCatalogMapPlaques(grid);
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
      appendCatalogMapPlaque(card, primaryCityKeyFromFilters(row.details?.filters));
      card.appendChild(createTextNode("h3", cleanCardTitle(row.title)));
      appendCardFacts(card, row);
      fragment.appendChild(card);
    });

    grid.replaceChildren(fragment);
    initLocalVideoPosters(grid);
    initCatalogMapPlaques(grid);
  }

  const SIMILAR_FILTER_WEIGHTS = {
    city: 5,
    beach: 4,
    price: 3,
    distance: 3,
    stay: 2,
    food: 1,
    room: 1,
  };

  const PRICE_LABELS = {
    economy: "эконом",
    comfort: "комфорт",
    premium: "премиум",
  };

  const BEACH_LABELS = {
    [BEACH_FILTERS.SAND_LDZAA]: "песчаный пляж Лдзаа",
    [BEACH_FILTERS.SAND_SUKHUM]: "песчаный пляж Сухум",
    [BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA]: "сосновый галечный",
    [BEACH_FILTERS.PITSUNDA_BAY_MIXED]: "бухта Пицунда",
    [BEACH_FILTERS.PEBBLE]: "галечный пляж",
  };

  function normalizeListingFiltersMap(filters) {
    const map = {};
    FILTER_GROUPS.forEach((group) => {
      const raw = filters?.[group];
      const values = Array.isArray(raw)
        ? raw.map((value) => String(value || "").trim()).filter(Boolean)
        : String(raw || "")
            .split("|")
            .map((value) => value.trim())
            .filter(Boolean);
      map[group] = new Set(values);
    });
    return map;
  }

  function filterSimilarityScore(baseMap, candidateMap) {
    let score = 0;
    FILTER_GROUPS.forEach((group) => {
      const weight = SIMILAR_FILTER_WEIGHTS[group] || 1;
      const left = baseMap[group];
      const right = candidateMap[group];
      if (!left?.size || !right?.size) return;
      left.forEach((token) => {
        if (right.has(token)) score += weight;
      });
    });
    return score;
  }

  function pickSimilarListings(currentRow, rows, limit = 3) {
    const baseMap = normalizeListingFiltersMap(currentRow?.details?.filters);
    const ranked = rows
      .filter((row) => row?.slug && row.slug !== currentRow.slug)
      .map((row) => ({
        row,
        score: filterSimilarityScore(baseMap, normalizeListingFiltersMap(row.details?.filters)),
      }))
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return String(a.row.title || "").localeCompare(String(b.row.title || ""), "ru");
      });

    const picked = [];
    const used = new Set([currentRow.slug]);

    ranked
      .filter((item) => item.score > 0)
      .forEach((item) => {
        if (picked.length >= limit) return;
        if (used.has(item.row.slug)) return;
        picked.push(item.row);
        used.add(item.row.slug);
      });

    if (picked.length < 3) {
      ranked.forEach((item) => {
        if (picked.length >= limit) return;
        if (used.has(item.row.slug)) return;
        picked.push(item.row);
        used.add(item.row.slug);
      });
    }

    return picked.slice(0, limit);
  }

  function buildSimilarSectionLead(currentRow) {
    const filters = currentRow?.details?.filters || {};
    const hints = [];
    const city = CITY_LABELS[firstValue(filters.city)];
    const beach = BEACH_LABELS[firstValue(filters.beach)];
    const price = PRICE_LABELS[firstValue(filters.price)];
    const distance = DISTANCE_BY_FILTER[firstValue(filters.distance)];
    if (city) hints.push(city);
    if (beach) hints.push(beach);
    if (price) hints.push(`бюджет «${price}»`);
    if (distance) hints.push(distance);
    if (!hints.length) {
      return "Ещё варианты с похожими параметрами — можно сравнить и перейти дальше без возврата в каталог.";
    }
    return `Подборка по схожим параметрам: ${hints.join(", ")}.`;
  }

  function buildSimilarCatalogCard(row, sourceKind) {
    const card = document.createElement("a");
    card.className = "catalog-card";
    card.href = pathnameFromUrl(
      row.page_url,
      sourceKind === "kvartira" ? `/kvartira/${row.slug}/` : `/hotels/${row.slug}/`
    );
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
    card.appendChild(createTextNode("h3", cleanCardTitle(row.title)));
    appendCardFacts(card, { ...row, source_kind: row.source_kind || sourceKind });

    return card;
  }

  let blogPostsCache = null;

  async function fetchBlogPosts() {
    if (blogPostsCache) return blogPostsCache;
    const response = await fetch("/data/blog-posts.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("blog-posts.json unavailable");
    const posts = await response.json();
    blogPostsCache = Array.isArray(posts) ? posts : [];
    return blogPostsCache;
  }

  function normalizeBlogTags(tags) {
    return new Set(
      (tags || [])
        .map((tag) => String(tag || "").trim().toLowerCase())
        .filter(Boolean)
    );
  }

  function blogSimilarityScore(baseTags, post) {
    const postTags = normalizeBlogTags([...(post?.tags || []), post?.card_tag]);
    let score = 0;
    baseTags.forEach((tag) => {
      if (postTags.has(tag)) score += 2;
    });
    return score;
  }

  function pickSimilarBlogPosts(currentSlug, currentTags, posts, limit = 3) {
    const baseTags = normalizeBlogTags(currentTags);
    const ranked = posts
      .filter((post) => post?.slug && post.slug !== currentSlug)
      .map((post) => ({
        post,
        score: blogSimilarityScore(baseTags, post),
      }))
      .sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        return String(right.post.iso_date || "").localeCompare(String(left.post.iso_date || ""), "ru");
      });

    const picked = [];
    const used = new Set([currentSlug]);

    ranked
      .filter((item) => item.score > 0)
      .forEach((item) => {
        if (picked.length >= limit) return;
        if (used.has(item.post.slug)) return;
        picked.push(item.post);
        used.add(item.post.slug);
      });

    if (picked.length < limit) {
      ranked.forEach((item) => {
        if (picked.length >= limit) return;
        if (used.has(item.post.slug)) return;
        picked.push(item.post);
        used.add(item.post.slug);
      });
    }

    return picked.slice(0, limit);
  }

  function buildSimilarBlogLead(currentTags, posts) {
    const shared = [];
    const baseTags = normalizeBlogTags(currentTags);
    posts.forEach((post) => {
      normalizeBlogTags([...(post.tags || []), post.card_tag]).forEach((tag) => {
        if (baseTags.has(tag) && !shared.includes(tag)) shared.push(tag);
      });
    });
    if (!shared.length) {
      return "Ещё материалы из раздела «Полезно узнать» — можно почитать без возврата к списку статей.";
    }
    const labels = shared.slice(0, 3).map((tag) => tag.charAt(0).toUpperCase() + tag.slice(1));
    return `Подборка по теме: ${labels.join(", ")}.`;
  }

  function blogCardImageSrc(post) {
    const raw = String(post?.image || "").trim();
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw)) return raw;
    return `https://storage.yandexcloud.net/abhazbereg-media/media/blog/${raw.replace(/^\/+/, "")}`;
  }

  function blogCardImageSrcset(src) {
    const clean = String(src || "").split("?")[0];
    const stem = clean.replace(/\.(?:jpe?g|png|webp)$/i, "");
    if (!stem || stem === clean) return "";
    return [480, 960, 1440].map((width) => `${stem}-${width}.webp ${width}w`).join(", ");
  }

  function buildSimilarBlogCard(post) {
    const article = document.createElement("article");
    article.className = "blog-card";
    const href = `/blog/${post.slug}/`;
    const date = formatPublishedDate(post.iso_date);
    const imageSrc = blogCardImageSrc(post);

    const imageLink = document.createElement("a");
    imageLink.className = "blog-card__image-link";
    imageLink.href = href;
    if (imageSrc) {
      const image = document.createElement("img");
      image.loading = "lazy";
      image.decoding = "async";
      image.alt = post.title || "";
      image.src = imageSrc;
      image.srcset = blogCardImageSrcset(imageSrc);
      image.sizes = "(max-width: 760px) 100vw, 220px";
      image.width = 480;
      image.height = 330;
      imageLink.appendChild(image);
    }
    article.appendChild(imageLink);

    const body = document.createElement("div");
    body.className = "blog-card__body";

    const meta = document.createElement("p");
    meta.className = "blog-card__meta";
    const tag = document.createElement("span");
    tag.textContent = post.card_tag || "блог";
    meta.appendChild(tag);
    if (date) {
      const time = document.createElement("time");
      time.dateTime = date.machine;
      time.textContent = date.human;
      meta.appendChild(time);
    }
    body.appendChild(meta);

    const title = document.createElement("h3");
    const titleLink = document.createElement("a");
    titleLink.href = href;
    titleLink.textContent = post.title || "";
    title.appendChild(titleLink);
    body.appendChild(title);

    body.appendChild(createTextNode("p", post.excerpt || ""));

    const cta = document.createElement("a");
    cta.className = "blog-card__cta";
    cta.href = href;
    cta.textContent = "Читать статью";
    body.appendChild(cta);

    article.appendChild(body);
    return article;
  }

  async function initSimilarBlogPosts() {
    const match = window.location.pathname.match(/^\/blog\/([^/]+)\/?$/);
    if (!match) return;

    const slug = decodeURIComponent(match[1]);
    if (!slug) return;

    const main = document.querySelector("main.blog-article-page");
    const anchor = main?.querySelector("article.blog-article");
    if (!main || !anchor) return;

    let section = main.querySelector("[data-similar-blog]");
    if (!section) {
      section = document.createElement("section");
      section.className = "site-concept__section-block blog-article__similar";
      section.setAttribute("data-similar-blog", "");
      section.hidden = true;
      section.setAttribute("aria-label", "Другие статьи блога");
      section.innerHTML = `
        <div class="blog-article__similar-head">
          <p class="site-concept__eyebrow">Ещё из блога</p>
          <h2>Может быть полезно по теме</h2>
          <p class="blog-article__similar-lead"></p>
        </div>
        <div class="blog-grid blog-article__similar-grid" data-similar-blog-grid></div>
      `;
      anchor.insertAdjacentElement("afterend", section);
    }

    const leadNode = section.querySelector(".blog-article__similar-lead");
    const grid = section.querySelector("[data-similar-blog-grid]");
    if (!leadNode || !grid) return;

    try {
      const posts = await fetchBlogPosts();
      if (posts.length < 2) return;

      const currentTags = [...document.querySelectorAll(".blog-article .blog-tags span")]
        .map((node) => node.textContent.trim())
        .filter(Boolean);
      const similarPosts = pickSimilarBlogPosts(slug, currentTags, posts, 3);
      if (similarPosts.length < 2) return;

      leadNode.textContent = buildSimilarBlogLead(currentTags, similarPosts);
      const fragment = document.createDocumentFragment();
      similarPosts.forEach((post) => fragment.appendChild(buildSimilarBlogCard(post)));
      grid.replaceChildren(fragment);
      section.hidden = false;
    } catch (error) {
      console.warn("Не удалось показать похожие статьи блога", error);
    }
  }

  async function initSimilarListings() {
    const hotelMatch = window.location.pathname.match(/^\/hotels\/([^/]+)\/?$/);
    const kvMatch = window.location.pathname.match(/^\/kvartira\/([^/]+)\/?$/);
    if (!hotelMatch && !kvMatch) return;

    const slug = hotelMatch?.[1] || kvMatch?.[1];
    const sourceKind = hotelMatch ? "hotel" : "kvartira";
    if (sourceKind === "kvartira" && KVARTIRA_EXCLUDED_SLUGS.has(slug)) return;

    const main = document.querySelector("main.hotel-site-concept");
    const anchor = main?.querySelector(".hotel-site-concept__detail-grid");
    if (!main || !anchor) return;

    let section = main.querySelector("[data-similar-listings]");
    if (!section) {
      section = document.createElement("section");
      section.className = "section hotel-site-concept__similar";
      section.setAttribute("data-similar-listings", "");
      section.hidden = true;
      section.innerHTML = `
        <div class="hotel-site-concept__similar-head">
          <p class="eyebrow">Похожие варианты</p>
          <h2>Может подойти, если смотрите рядом</h2>
          <p class="hotel-site-concept__similar-lead"></p>
        </div>
        <div class="catalog-grid hotel-site-concept__similar-grid" data-similar-listings-grid></div>
      `;
      anchor.insertAdjacentElement("afterend", section);
    }

    const leadNode = section.querySelector(".hotel-site-concept__similar-lead");
    const grid = section.querySelector("[data-similar-listings-grid]");
    if (!leadNode || !grid) return;

    try {
      const currentRow = await fetchListingBySlug(slug);
      if (!currentRow) return;

      const allRows = await fetchListings({ sourceKind });
      const similarRows = pickSimilarListings(
        currentRow,
        (allRows || []).filter((row) => row.slug && !KVARTIRA_EXCLUDED_SLUGS.has(row.slug)),
        3
      );
      if (similarRows.length < 2) return;

      leadNode.textContent = buildSimilarSectionLead(currentRow);
      const fragment = document.createDocumentFragment();
      similarRows.forEach((row) => fragment.appendChild(buildSimilarCatalogCard(row, sourceKind)));
      grid.replaceChildren(fragment);
      initLocalVideoPosters(grid);
      section.hidden = false;
    } catch (error) {
      console.warn("Не удалось показать похожие объекты", error);
    }
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

  function resolveMediaUrl(item, row) {
    if (item && typeof item.source_url === "string" && item.source_url.startsWith("/media/")) {
      return toCdnMediaUrl(item.source_url);
    }
    if (item && item.public_url) return toCdnMediaUrl(item.public_url);
    const raw = (item && item.storage_path) || (item && item.source_url) || '';
    if (!raw) return '';
    if (/^https?:\/\//i.test(raw)) {
      return toCdnMediaUrl(raw);
    }
    const rel = raw.replace(/^\/+/, '');
    return toCdnMediaUrl(`/media/${rel}`);
  }

  function renderHotelMedia(row, grid) {
    const fragment = document.createDocumentFragment();
    const media = Array.isArray(row.listing_media) ? [...row.listing_media] : [];
    media
      .filter((item) => item.media_role !== "card" && (item.public_url || item.storage_path || item.source_url || item.mime_type === "application/x-telegram-embed" || (item.details && item.details.telegram_post)))
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .forEach((item, index) => {
        if ((item.mime_type || "").startsWith("video/")) {
          const resolvedUrl = resolveMediaUrl(item, row);
          if (!resolvedUrl) return;
          const video = document.createElement("video");
          video.className = "local-video";
          video.controls = true;
          video.preload = "none";
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

        const resolvedUrl = resolveMediaUrl(item, row);
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
      initLocalVideoPosters(grid);
    }
  }

  function cardCatalogCategoryText(card) {
    const h3 = card.querySelector("h3");
    const img = card.querySelector("img");
    return `${h3?.textContent || ""} ${img?.getAttribute("alt") || ""}`.toLowerCase();
  }

  /** Нормализация заголовка карточки для поиска только по названию объекта (h3). */
  function normalizeCatalogTitle(text) {
    return String(text || "")
      .replace(/\u00a0/g, " ")
      .replace(/[«»""„"]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function getCatalogCardTitleText(card) {
    return card?.querySelector("h3")?.textContent || "";
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

  /**
   * Стор выбора фильтров: committed + мобильный draft, без DOM.
   * initFilters синхронизирует видимость карточек, URL и UI с полями стора.
   */
  function createFilterStore(groupOrder) {
    function cloneSelections(source) {
      const clone = {};
      groupOrder.forEach((g) => {
        clone[g] = new Set(source[g] || []);
      });
      return clone;
    }

    const emptySelections = () =>
      Object.fromEntries(groupOrder.map((group) => [group, new Set()]));

    const store = {
      subscribers: new Set(),
      committedSel: emptySelections(),
      committedCat: null,
      committedNameQuery: "",
      draftSel: emptySelections(),
      draftCat: null,
      draftNameQuery: "",

      cloneSelections,

      subscribe(listener) {
        if (typeof listener !== "function") {
          return () => {};
        }
        store.subscribers.add(listener);
        return () => store.subscribers.delete(listener);
      },

      replaceCommittedFromDraft() {
        store.committedSel = cloneSelections(store.draftSel);
        store.committedCat = store.draftCat;
        store.committedNameQuery = store.draftNameQuery;
      },

      syncDraftFromCommitted() {
        store.draftSel = cloneSelections(store.committedSel);
        store.draftCat = store.committedCat;
        store.draftNameQuery = store.committedNameQuery;
      },

      getCommittedSnapshot() {
        return {
          catalogCategory: store.committedCat,
          nameQuery: store.committedNameQuery,
          groups: Object.fromEntries(
            groupOrder.map((group) => [group, [...store.committedSel[group]]])
          ),
        };
      },
    };

    store.syncDraftFromCommitted();
    return store;
  }

  /** Сборка фильтров в query и обратное чтение при загрузке; не трогает DOM каталога. */
  function attachCatalogFilterUrlLayers(ctx) {
    const {
      isSuppressed,
      filt,
      filterGroups,
      catalogParamKey,
      categoryLabels,
      normalizeSelectedFilterTokens,
      rebuildRecentStackFromSelectionsFn,
    } = ctx;

    function syncCommittedToLocation() {
      if (isSuppressed()) return;
      const params = new URLSearchParams();
      if (filt.committedCat && categoryLabels[filt.committedCat]) {
        params.set(catalogParamKey, filt.committedCat);
      }
      filterGroups.forEach((group) => {
        const parts = [...filt.committedSel[group]].filter(Boolean).sort();
        if (!parts.length) return;
        params.set(group, parts.join(","));
      });

      const nameQuery = String(filt.committedNameQuery || "").trim();
      if (nameQuery) params.set("name", nameQuery);

      const nextSearch = params.toString() ? `?${params}` : "";
      const next = `${window.location.pathname}${nextSearch}${window.location.hash || ""}`;
      const current = `${window.location.pathname}${window.location.search}${window.location.hash || ""}`;
      if (next !== current) window.history.replaceState(null, "", next);
    }

    function absorbLocationIntoCommitted() {
      const params = new URLSearchParams(window.location.search || "");
      if (!params.toString()) return;

      filterGroups.forEach((group) => {
        filt.committedSel[group].clear();
        const blob = params.get(group);
        if (!blob) return;
        blob
          .split(",")
          .map((segment) => String(segment || "").trim())
          .filter(Boolean)
          .forEach((rawToken) => {
            normalizeSelectedFilterTokens(group, rawToken, "").forEach((token) => {
              if (token) filt.committedSel[group].add(token);
            });
          });
      });

      const cat = String(params.get(catalogParamKey) || "").trim();
      if (cat === "hotel" || cat === "guesthouse" || cat === "cabin") filt.committedCat = cat;
      else filt.committedCat = null;

      filt.committedNameQuery = String(params.get("name") || "").trim();
      filt.draftNameQuery = filt.committedNameQuery;

      rebuildRecentStackFromSelectionsFn();
    }

    return { syncCommittedToLocation, absorbLocationIntoCommitted };
  }

  /** Нижний лист / боковая панель фильтров на главной каталог-панели. */
  function attachFiltersDrawerInteractions(spec) {
    const { state } = spec;

    function openFiltersModal() {
      if (!spec.filtersModal) return;
      state.reopenFocusEl = document.activeElement;
      state.isOpen = true;
      if (spec.mobileDraftHint) spec.mobileDraftHint.hidden = !spec.isMobileFiltersLayout();
      spec.filt.syncDraftFromCommitted();
      const previewN = spec.countShownDraft(spec.filt.draftSel, spec.filt.draftCat);
      spec.onDraftPreviewCount(previewN);
      spec.filtersModal.hidden = false;
      requestAnimationFrame(() => spec.filtersModal.classList.add("is-visible"));
      spec.body.classList.add("modal-open");
      spec.syncChipUi(spec.filt.draftSel, spec.filt.draftCat);
      spec.syncApplyFooterText();
      spec.trackAnalytics("open_filters");
    }

    function closeFiltersModal(opts) {
      const restoreCommittedDraft = !(opts && opts.restoreCommittedDraft === false);
      if (!spec.filtersModal) return;
      if (restoreCommittedDraft && state.isOpen && spec.isMobileFiltersLayout()) {
        spec.rollbackDraftFromCommitted();
      }
      spec.filtersModal.classList.remove("is-visible");
      spec.body.classList.remove("modal-open");
      state.isOpen = false;
      if (spec.mobileDraftHint) spec.mobileDraftHint.hidden = true;
      spec.syncChipUi(spec.filt.committedSel, spec.filt.committedCat);

      window.setTimeout(() => {
        if (!spec.filtersModal.classList.contains("is-visible")) {
          spec.filtersModal.hidden = true;
        }
      }, 360);

      const focusTarget = state.reopenFocusEl || spec.openFiltersBtn;
      state.reopenFocusEl = null;
      if (focusTarget instanceof HTMLElement && typeof focusTarget.focus === "function") {
        window.requestAnimationFrame(() => focusTarget.focus({ preventScroll: true }));
      }
    }

    return { openFiltersModal, closeFiltersModal };
  }

  /** Индекс `data-filter` по карточкам единого каталога (#catalog-grid). */
  function buildCatalogCardIndexRecords(cards, groupOrder, parseCardGroup) {
    return cards.map((card) => ({
      el: card,
      titleNorm: normalizeCatalogTitle(getCatalogCardTitleText(card)),
      byGroup: Object.fromEntries(
        groupOrder.map((group) => [group, new Set(parseCardGroup(card, group).filter(Boolean))])
      ),
    }));
  }

  /** AND между группами; внутри группы — OR или AND по FILTER_CONFIG. */
  function filterGroupCombineMode(group) {
    const overrides = FILTER_CONFIG.combineWithinGroupByGroup;
    if (overrides && overrides[group]) return overrides[group];
    return FILTER_CONFIG.combineWithinGroup || "any";
  }

  /**
   * Расстояние — иерархия, а не категории: каждый уровень включает все
   * более близкие. «Больше 10 минут» = расстояние не важно, все объекты.
   */
  const DISTANCE_FILTER_EXPANSION = {
    "up-to-5": ["beachfront", "up-to-5"],
    "up-to-10": ["beachfront", "up-to-5", "up-to-10"],
    "over-10": ["beachfront", "up-to-5", "up-to-10", "over-10"],
  };

  function expandSelectedGroupValues(group, selectedSet) {
    if (group !== "distance") return selectedSet;
    const expanded = new Set();
    selectedSet.forEach((choice) => {
      const extra = DISTANCE_FILTER_EXPANSION[choice];
      if (extra) {
        extra.forEach((value) => expanded.add(value));
      } else {
        expanded.add(choice);
      }
    });
    return expanded;
  }

  function catalogIndexedEntryPassesFilters(
    entry,
    selected,
    slug,
    filterGroups,
    matchesCatalogSlug,
    catalogTextForCard,
    nameQuery
  ) {
    for (const group of filterGroups) {
      if (!selected[group] || selected[group].size === 0) continue;
      const bucket = entry.byGroup[group];
      const combineMode = filterGroupCombineMode(group);
      const choices = expandSelectedGroupValues(group, selected[group]);
      if (combineMode === "all") {
        for (const choice of choices) {
          if (!bucket.has(choice)) return false;
        }
      } else {
        let ok = false;
        for (const choice of choices) {
          if (bucket.has(choice)) {
            ok = true;
            break;
          }
        }
        if (!ok) return false;
      }
    }
    if (slug && !matchesCatalogSlug(slug, catalogTextForCard(entry.el))) {
      return false;
    }
    const normalizedNameQuery = normalizeCatalogTitle(nameQuery);
    if (normalizedNameQuery && !entry.titleNorm.includes(normalizedNameQuery)) {
      return false;
    }
    return true;
  }

  function attachCatalogCardFilterMatching(deps) {
    let entries = [];

    function rebuild() {
      entries = buildCatalogCardIndexRecords(deps.collectCards(), deps.filterGroups, deps.parseCardGroup);
    }

    function passes(entry, selected, catSlug, nameQuery) {
      return catalogIndexedEntryPassesFilters(
        entry,
        selected,
        catSlug,
        deps.filterGroups,
        deps.matchesCatalogSlug,
        deps.catalogTextForCard,
        nameQuery
      );
    }

    function countHotelShown(selected, catSlug, nameQuery) {
      let shown = 0;
      entries.forEach((entry) => {
        if (!passes(entry, selected, catSlug, nameQuery)) return;
        if (isHotelCatalogCard(entry.el)) shown += 1;
      });
      return shown;
    }

    function countAllMatching(selected, catSlug, nameQuery) {
      let n = 0;
      entries.forEach((entry) => {
        if (passes(entry, selected, catSlug, nameQuery)) n += 1;
      });
      return n;
    }

    function applyHiddenForSelection(selected, catSlug, nameQuery) {
      let hotelShown = 0;
      let totalShown = 0;
      entries.forEach((entry) => {
        const ok = passes(entry, selected, catSlug, nameQuery);
        entry.el.hidden = !ok;
        if (!ok) return;
        totalShown += 1;
        if (isHotelCatalogCard(entry.el)) hotelShown += 1;
      });
      return { hotelShown, totalShown };
    }

    return { rebuild, passes, countHotelShown, countAllMatching, applyHiddenForSelection };
  }

  function deferCatalogCardImages(cards, immediateLimit) {
    (cards || []).forEach((card, index) => {
      card.dataset.catalogIndex = String(index);
      card.querySelectorAll("img[src]").forEach((img) => {
        img.decoding = "async";
        if (index < immediateLimit) {
          if (index < 4) img.fetchPriority = "high";
          return;
        }
        if (img.dataset.deferredSrc) return;
        img.dataset.deferredSrc = img.getAttribute("src") || "";
        img.dataset.deferredSrcset = img.getAttribute("srcset") || "";
        img.dataset.deferredSizes = img.getAttribute("sizes") || "";
        img.removeAttribute("src");
        img.removeAttribute("srcset");
        img.removeAttribute("sizes");
        img.loading = "lazy";
      });
    });
  }

  function restoreCatalogCardImages(cards) {
    (cards || []).forEach((card) => {
      if (card.hidden) return;
      card.querySelectorAll("img[data-deferred-src]").forEach((img) => {
        const src = img.dataset.deferredSrc || "";
        if (!src) return;
        img.setAttribute("src", src);
        if (img.dataset.deferredSrcset) img.setAttribute("srcset", img.dataset.deferredSrcset);
        if (img.dataset.deferredSizes) img.setAttribute("sizes", img.dataset.deferredSizes);
        img.removeAttribute("data-deferred-src");
        img.removeAttribute("data-deferred-srcset");
        img.removeAttribute("data-deferred-sizes");
      });
    });
  }

  /** Склонение для строки «ничего не нашли по N фильтру/фильтрам» над пустым каталогом. */
  function parametrovSklonenieRuForFilters(n) {
    const k = Number(n);
    if (!Number.isFinite(k) || k <= 0) return "выбранным фильтрам";
    const mod100 = k % 100;
    const mod10 = k % 10;
    if (mod100 >= 11 && mod100 <= 14) return `${k} фильтрам`;
    if (mod10 === 1) return `${k} фильтру`;
    return `${k} фильтрам`;
  }

  /** Плашки снятия фильтров, подпись кнопки «Фильтры», текст пустого блока результатов. */
  function attachCatalogFilterSummaryChrome(spec) {
    const d = spec;

    function renderActiveRemovalChips() {
      if (!d.activeFiltersList || !d.activeFiltersWrap) return;
      d.activeFiltersList.replaceChildren();

      d.filterGroups.forEach((group) => {
        [...d.filt.committedSel[group]].forEach((token) => {
          const label = d.resolveTokenLabel(group, token);
          if (!label) return;
          const chip = document.createElement("button");
          chip.type = "button";
          chip.className = "filter-pill-removable";
          chip.setAttribute("data-remove-group", group);
          chip.setAttribute("data-remove-token", token);
          chip.setAttribute("aria-label", `Снять фильтр «${label}»`);
          chip.innerHTML = `${label}<span class="filter-pill-removable__x" aria-hidden="true">\u00d7</span>`;
          d.activeFiltersList.appendChild(chip);
        });
      });

      if (d.filt.committedCat && d.categoryLabels[d.filt.committedCat]) {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "filter-pill-removable filter-pill-removable--muted";
        pill.setAttribute("data-remove-category", "1");
        pill.setAttribute("aria-label", `Снять «${d.categoryLabels[d.filt.committedCat]}»`);
        pill.innerHTML =
          `${d.categoryLabels[d.filt.committedCat]}<span class="filter-pill-removable__x" aria-hidden="true">\u00d7</span>`;
        d.activeFiltersList.appendChild(pill);
      }

      const nameQuery = String(d.filt.committedNameQuery || "").trim();
      if (nameQuery) {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "filter-pill-removable";
        pill.setAttribute("data-remove-name", "1");
        pill.setAttribute("aria-label", `Снять поиск «${nameQuery}»`);
        pill.append(`Название: «${nameQuery}»`);
        const x = document.createElement("span");
        x.className = "filter-pill-removable__x";
        x.setAttribute("aria-hidden", "true");
        x.textContent = "\u00d7";
        pill.appendChild(x);
        d.activeFiltersList.appendChild(pill);
      }

      d.activeFiltersWrap.hidden = d.countPins(d.filt.committedSel, d.filt.committedCat, d.filt.committedNameQuery) === 0;
    }

    function syncOpenBadge() {
      const pins = d.countPins(d.filt.committedSel, d.filt.committedCat, d.filt.committedNameQuery);
      const cap = pins > 99 ? "99+" : String(pins);

      if (d.openFiltersLabel) {
        d.openFiltersLabel.textContent = pins ? `Фильтры · ${cap}` : "Фильтры";
      }
      if (d.openFiltersBadge) {
        d.openFiltersBadge.textContent = cap;
        d.openFiltersBadge.setAttribute("hidden", "");
      }
      if (d.openFiltersBtn) {
        d.openFiltersBtn.setAttribute("aria-label", pins ? `Открыть фильтры · активно условий: ${pins}` : "Открыть фильтры");
      }
    }

    function updateEmptyLead(totalMatching, pins) {
      if (!d.emptyLeadEl || !d.emptyNoteEl) return;
      if (totalMatching > 0) return;

      const emptyHint = d.emptyNoteEl.querySelector(".filter-empty__hint");

      if (totalMatching === 0) {
        if (pins === 0) {
          d.emptyLeadEl.textContent =
            "По выбранным параметрам пока нет подходящих объектов. Ослабьте один из фильтров или сбросьте их.";
        } else {
          const filterWordParams = parametrovSklonenieRuForFilters(pins);
          d.emptyLeadEl.textContent = `Ничего не нашли по ${filterWordParams}. Ослабьте условие, снимите последний параметр или сбросьте всё.`;
        }
        if (emptyHint) {
          emptyHint.textContent = "Попробуйте смягчить условие: город, расстояние до пляжа или бюджет.";
          emptyHint.removeAttribute("hidden");
        }
      }
    }

    return { renderActiveRemovalChips, syncOpenBadge, updateEmptyLead };
  }

  function initFilters() {
    const FILTER_SHEET_MOBILE_QUERY = "(max-width: 900px)";

    const CATALOG_CATEGORY_LABELS = {
      hotel: "Тип размещения: отели",
      guesthouse: "Тип размещения: гостевые дома",
      cabin: "Тип размещения: домики и коттеджи",
    };

    const grid = document.getElementById("catalog-grid");
    if (!grid) {
      const noopUnsub = () => {};
      return {
        refresh: () => {},
        setCatalogCategory: () => {},
        setGroupValues: () => {},
        clearGroups: () => {},
        applySearchFromForm: () => {},
        applyPatch: () => {},
        setNameQuery: () => {},
        getNameQuery: () => "",
        subscribe: () => noopUnsub,
        getCommittedSnapshot: () => null,
      };
    }

    const selectionHero = document.getElementById("selection-podborka-hero");
    const selectionView = document.getElementById("selection-podborka-view");
    const selectionTitle = document.getElementById("selection-podborka-title");
    const selectionCount = document.getElementById("selection-podborka-count");
    const shareSelectionBtn = document.getElementById("share-selection-link");
    const shareSelectionHeroBtn = document.getElementById("share-selection-link-hero");
    const editSelectionFiltersBtn = document.getElementById("edit-selection-filters");

    function isMobileFiltersLayout() {
      return window.matchMedia(FILTER_SHEET_MOBILE_QUERY).matches;
    }

    const filt = createFilterStore(FILTER_GROUPS);
    let recentStack = [];
    let suppressUrlSync = false;

    const chipCaptionBySig = new Map();
    Array.from(document.querySelectorAll(".filter-chip")).forEach((chipEl) => {
      const grp = chipEl.dataset.group || "";
      const val = chipEl.dataset.value || "";
      if (!grp || !val) return;
      const sig = `${grp}:${String(val).trim()}`.toLowerCase();
      if (!chipCaptionBySig.has(sig)) {
        chipCaptionBySig.set(sig, (chipEl.textContent || "").replace(/\s+/g, " ").trim() || val);
      }
    });

    const chips = Array.from(document.querySelectorAll(".filter-chip"));
    const visibleCount = document.getElementById("visible-count");
    const emptyNote = document.getElementById("filter-empty");
    const emptyLead = document.getElementById("filter-empty-message");
    const emptyRemoveLastBtn = document.getElementById("filter-empty-remove-last");
    const emptyResetBtn = document.getElementById("filter-empty-reset");
    const clearBtn = document.getElementById("clear-filters");
    const activeFiltersWrap = document.getElementById("active-filters");
    const activeFiltersList = document.getElementById("active-filters-list");
    const openFiltersBtn = document.getElementById("open-filters");
    const openFiltersLabel = document.getElementById("open-filters-label");
    const openFiltersBadge = document.getElementById("open-filters-badge");
    const filtersModal = document.getElementById("filters-modal");
    const closeFilterEls = Array.from(document.querySelectorAll("[data-close-filters]"));
    const applyFiltersBtn = document.getElementById("apply-filters");
    const modalResetDraftBtn = document.getElementById("filters-modal-reset");
    const mobileDraftHint = document.getElementById("filters-draft-hint-mobile");
    const filtersDraftPreview = document.getElementById("filters-draft-preview");
    const catalogExpandBtn = document.getElementById("catalog-expand-button");

    let draftPreviewCount = 0;
    let catalogExpanded = false;
    const CATALOG_INITIAL_LIMIT = 20;
    let catalogMediaDeferred = false;
    let catalogIndexReady = false;

    const filtersDrawerState = { reopenFocusEl: null, isOpen: false };

    function pickWorkingSets() {
      if (filtersDrawerState.isOpen && isMobileFiltersLayout()) {
        return { selected: filt.draftSel, categorySlug: filt.draftCat, isDraftFlow: true };
      }
      return { selected: filt.committedSel, categorySlug: filt.committedCat, isDraftFlow: false };
    }

    function getCards() {
      return Array.from(grid.querySelectorAll(".catalog-card"));
    }

    function parseValues(card, group) {
      const key = `filter${group.charAt(0).toUpperCase()}${group.slice(1)}`;
      const raw = card.dataset[key] || "";
      const normalized = normalizeCardFilterValues(group, raw, card);
      if (normalized.length) return normalized;
      return inferCardFilterValues(group, card);
    }

    const catalogMatch = attachCatalogCardFilterMatching({
      collectCards: getCards,
      filterGroups: FILTER_GROUPS,
      parseCardGroup: parseValues,
      matchesCatalogSlug: matchesCatalogCategory,
      catalogTextForCard: cardCatalogCategoryText,
    });

    function normalizeSelectedFilterValues(group, value, chipText) {
      const raw = String(value || "").trim();
      const label = String(chipText || "").toLowerCase();
      if (!raw) return [];

      if (group === "price") {
        const normalized = normalizePriceValue(raw);
        return normalized ? [normalized] : [];
      }

      if (group === "room") {
        const normalized = normalizeRoomValue(raw);
        return normalized ? [normalized] : [];
      }

      if (group === "stay") {
        const normalized = normalizeStayValue(raw);
        return normalized ? [normalized] : [];
      }

      if (group === "beach") {
        if (raw === "sand" || label.includes("песчаный")) {
          if (label.includes("сухум")) return [BEACH_FILTERS.SAND_SUKHUM];
          if (label.includes("лдзаа")) return [BEACH_FILTERS.SAND_LDZAA];
          return [BEACH_FILTERS.SAND_LDZAA, BEACH_FILTERS.SAND_SUKHUM];
        }
        if (raw === "pine-pebble" || label.includes("соснов")) return [BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA];
        if (raw === "mixed" || label.includes("бухта")) return [BEACH_FILTERS.PITSUNDA_BAY_MIXED];
        if (raw === "pebble" || label.includes("галеч")) return [BEACH_FILTERS.PEBBLE];
        const normalized = normalizeBeachValue(raw, []);
        return normalized ? [normalized] : [];
      }

      return [raw];
    }

    function isSelectedChip(selection, group, value, chipText) {
      if (!group || !value || !selection[group]) return false;
      const normalizedValues = normalizeSelectedFilterValues(group, value, chipText);
      if (!normalizedValues.length) return false;
      return normalizedValues.every((normalized) => selection[group].has(normalized));
    }

    function syncChipUi(selection, categorySlugUnused) {
      void categorySlugUnused;
      chips.forEach((chip) => {
        chip.type = "button";
        const group = chip.dataset.group;
        const value = chip.dataset.value;
        const active = Boolean(group && value && isSelectedChip(selection, group, value, chip.textContent));
        chip.classList.toggle("is-active", active);
        chip.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function rebuildCardIndex() {
      selectionPodborka.restoreCardsToGrid();
      catalogMatch.rebuild();
      catalogIndexReady = true;
      selectionPodborka.rememberAnchors();
    }

    function ensureCardIndex() {
      if (!catalogIndexReady) rebuildCardIndex();
    }

    function notifySubscribers(reason, snapshot) {
      const payload =
        snapshot && typeof snapshot === "object"
          ? { reason, ...snapshot }
          : {
              reason,
              pins: countActivePins(filt.committedSel, filt.committedCat, filt.committedNameQuery),
              primaryShown: 0,
              totalMatching: countTotalMatching(filt.committedSel, filt.committedCat, filt.committedNameQuery),
            };

      filt.subscribers.forEach((fn) => {
        try {
          fn(payload);
        } catch (_) {
          /* ignore listener errors */
        }
      });
    }

    function countShownOnly(selected, slug, nameQuery) {
      ensureCardIndex();
      return catalogMatch.countAllMatching(selected, slug, nameQuery ?? filt.committedNameQuery);
    }

    function countTotalMatching(selected, slug, nameQuery) {
      ensureCardIndex();
      return catalogMatch.countAllMatching(selected, slug, nameQuery ?? filt.committedNameQuery);
    }

    function applyVisibilityCommitted() {
      ensureCardIndex();
      return catalogMatch.applyHiddenForSelection(
        filt.committedSel,
        filt.committedCat,
        filt.committedNameQuery
      );
    }

    function labelForToken(group, token) {
      if (token && group === "beach") {
        if (token === BEACH_FILTERS.SAND_LDZAA) return "Песчаный пляж Лдзаа";
        if (token === BEACH_FILTERS.SAND_SUKHUM) return "Песчаный пляж Сухум";
        if (token === BEACH_FILTERS.PINE_PEBBLE_LDZAA_PITSUNDA) return "Сосновый галечный берег Лдзаа и Пицунда";
        if (token === BEACH_FILTERS.PITSUNDA_BAY_MIXED) return "Пицундская бухта";
        if (token === BEACH_FILTERS.PEBBLE) return "Галечные пляжи";
      }
      const slugSig = `${group}:${token}`.toLowerCase();
      if (chipCaptionBySig.has(slugSig)) return chipCaptionBySig.get(slugSig);
      if (token && group === "city" && CITY_LABELS[token]) return CITY_LABELS[token];
      if (group === "room" && token === "five-plus") return "5+ гостей";
      if (group === "room" && token === "two-room-plus") return "Две комнаты и более";
      if (token === "economy") return "Бюджет: до 5000 ₽ в сутки";
      if (token === "midrange") return "Бюджет: до 10000 ₽ в сутки";
      if (token === "premium") return "Бюджет: премиум";
      return token ? String(token) : "";
    }

    function countActivePins(selected, slug, nameQuery) {
      let n = FILTER_GROUPS.reduce((acc, group) => acc + selected[group].size, 0);
      if (slug) n += 1;
      if (String(nameQuery || "").trim()) n += 1;
      return n;
    }

    function syncCatalogInitialLimit(visibility, pins) {
      if (pins > 0) return visibility.totalShown;

      const cards = Array.from(grid.querySelectorAll(".catalog-card"));
      const shouldLimit = !catalogExpanded;
      let displayed = 0;

      cards.forEach((card) => {
        if (card.hidden) return;

        if (shouldLimit) {
          displayed += 1;
          if (displayed > CATALOG_INITIAL_LIMIT) {
            card.hidden = true;
          }
        }
      });

      if (catalogExpandBtn) {
        const needsExpand = visibility.totalShown > CATALOG_INITIAL_LIMIT;
        catalogExpandBtn.hidden = !(pins === 0 && !catalogExpanded && needsExpand);
      }

      restoreCatalogCardImages(cards.filter((card) => !card.hidden));

      return shouldLimit
        ? Math.min(visibility.totalShown, CATALOG_INITIAL_LIMIT)
        : visibility.totalShown;
    }

    function hasActiveCommittedFilters() {
      return countActivePins(filt.committedSel, filt.committedCat, filt.committedNameQuery) > 0;
    }

    const catalogMatchTotal = document.getElementById("catalog-match-total");

    function updateVisibleCountLabel(shown, totalMatching) {
      if (visibleCount) visibleCount.textContent = String(shown);
      if (catalogMatchTotal) catalogMatchTotal.textContent = String(totalMatching);
    }

    function applyInitialCatalogLimitWithoutIndex() {
      const cards = getCards();
      if (!catalogMediaDeferred) {
        deferCatalogCardImages(cards, CATALOG_INITIAL_LIMIT);
        catalogMediaDeferred = true;
      }

      let index = 0;
      cards.forEach((card) => {
        index += 1;
        card.hidden = index > CATALOG_INITIAL_LIMIT;
      });

      if (catalogExpandBtn) {
        catalogExpandBtn.hidden = cards.length <= CATALOG_INITIAL_LIMIT;
      }
      const shown = Math.min(cards.length, CATALOG_INITIAL_LIMIT);
      updateVisibleCountLabel(shown, cards.length);
      if (clearBtn) clearBtn.hidden = true;
      if (emptyNote) emptyNote.hidden = true;

      syncOpenBadge();
      renderActiveRemovalChips();
      syncChipUi(filt.committedSel, filt.committedCat);
      draftPreviewCount = shown;
      syncApplyFooterText();
      notifySubscribers("commit", {
        pins: 0,
        primaryShown: shown,
        totalMatching: cards.length,
        resultCount: shown,
      });
    }

    const { renderActiveRemovalChips, syncOpenBadge, updateEmptyLead } = attachCatalogFilterSummaryChrome({
      filt,
      filterGroups: FILTER_GROUPS,
      categoryLabels: CATALOG_CATEGORY_LABELS,
      resolveTokenLabel: labelForToken,
      countPins: countActivePins,
      activeFiltersWrap,
      activeFiltersList,
      openFiltersLabel,
      openFiltersBadge,
      openFiltersBtn,
      emptyLeadEl: emptyLead,
      emptyNoteEl: emptyNote,
    });

    function pushRecent(group, token) {
      if (group === "catalog" && token) {
        recentStack = recentStack.filter((item) => !(item.group === "catalog"));
        recentStack.push({ group: "catalog", token });
        return;
      }
      if (group === "name" && token) {
        recentStack = recentStack.filter((item) => !(item.group === "name"));
        recentStack.push({ group: "name", token });
        return;
      }
      if (!token || !FILTER_GROUPS.includes(group)) return;
      recentStack = recentStack.filter((item) => !(item.group === group && item.token === token));
      recentStack.push({ group, token });
    }

    function popLastRecent() {
      return recentStack.pop() || null;
    }

    function syncRecentRemoval(group, normalized, adding) {
      if (group === "catalog") return;
      if (adding) {
        pushRecent(group, normalized);
        return;
      }
      recentStack = recentStack.filter((item) => !(item.group === group && item.token === normalized));
    }

    function clearRecentFully() {
      recentStack = [];
    }

    function variantsWord(n) {
      const mod10 = n % 10;
      const mod100 = n % 100;
      if (mod10 === 1 && mod100 !== 11) return "вариант";
      if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "варианта";
      return "вариантов";
    }

    function syncApplyFooterText() {
      if (!applyFiltersBtn) return;
      const mobile = filtersDrawerState.isOpen && isMobileFiltersLayout();

      if (filtersDraftPreview) {
        if (mobile) {
          filtersDraftPreview.removeAttribute("hidden");
          const previewN = draftPreviewCount;
          filtersDraftPreview.textContent = `Найдено ${previewN} ${variantsWord(previewN)} по выбранным условиям`;
        } else {
          filtersDraftPreview.setAttribute("hidden", "");
        }
      }

      if (!mobile || !filtersDrawerState.isOpen) {
        applyFiltersBtn.textContent = "Готово";
        applyFiltersBtn.removeAttribute("aria-label");
        return;
      }

      const countShown = draftPreviewCount;
      applyFiltersBtn.textContent = `Показать ${countShown} ${variantsWord(countShown)}`;
      applyFiltersBtn.removeAttribute("aria-label");
    }

    function rebuildRecentStackFromSelections() {
      recentStack = [];
      if (filt.committedCat) pushRecent("catalog", filt.committedCat);
      if (filt.committedNameQuery) pushRecent("name", filt.committedNameQuery);
      FILTER_GROUPS.forEach((group) => {
        [...filt.committedSel[group]].forEach((token) => pushRecent(group, token));
      });
    }

    function syncNameSearchInputs(value) {
      const normalized = String(value || "");
      ["search-name", "catalog-name-search"].forEach((id) => {
        const input = document.getElementById(id);
        if (input && input.value !== normalized) input.value = normalized;
      });
    }

    function setNameQuery(value) {
      const next = String(value || "").trim();
      if (next === filt.committedNameQuery) return;

      filt.committedNameQuery = next;
      filt.draftNameQuery = next;
      if (next) pushRecent("name", next);
      else recentStack = recentStack.filter((item) => item.group !== "name");

      syncNameSearchInputs(next);
      rollbackDraftFromCommitted();
      applyCommittedToDom();
    }

    const catalogUrl = attachCatalogFilterUrlLayers({
      isSuppressed: () => suppressUrlSync,
      filt,
      filterGroups: FILTER_GROUPS,
      catalogParamKey: FILTER_CONFIG.catalogParamKey,
      categoryLabels: CATALOG_CATEGORY_LABELS,
      normalizeSelectedFilterTokens: normalizeSelectedFilterValues,
      rebuildRecentStackFromSelectionsFn: rebuildRecentStackFromSelections,
    });

    function toggleTokensInSelection(selection, group, normalizedValues, enable, trackRecent, treatAsCategory) {
      if (treatAsCategory) return;
      if (!normalizedValues.length || !selection[group]) return;

      normalizedValues.forEach((normalized) => {
        if (!normalized) return;
        if (enable) {
          selection[group].add(normalized);
          if (trackRecent !== false) syncRecentRemoval(group, normalized, true);
        } else {
          selection[group].delete(normalized);
          if (trackRecent !== false) syncRecentRemoval(group, normalized, false);
        }
      });
    }

    function applyCommittedFromDraft() {
      filt.replaceCommittedFromDraft();
      rebuildRecentStackFromSelections();
      applyCommittedToDom();
    }

    function rollbackDraftFromCommitted() {
      filt.syncDraftFromCommitted();
      draftPreviewCount = countShownOnly(filt.draftSel, filt.draftCat);
      syncApplyFooterText();
      syncChipUi(filt.draftSel, filt.draftCat);
    }

    function applyCommittedToDom() {
      const visibility = applyVisibilityCommitted();
      const pins = countActivePins(filt.committedSel, filt.committedCat, filt.committedNameQuery);
      const totalMatching = visibility.totalShown;
      let resultCount = totalMatching;

      const visibleCards = Array.from(grid.querySelectorAll(".catalog-card")).filter((card) => !card.hidden);
      restoreCatalogCardImages(visibleCards);

      if (pins > 0) {
        selectionPodborka.sync(totalMatching, pins);
        if (emptyNote) emptyNote.hidden = totalMatching !== 0;
      } else {
        selectionPodborka.sync(0, 0);
        resultCount = syncCatalogInitialLimit(visibility, pins);
        if (emptyNote) emptyNote.hidden = true;
      }

      updateVisibleCountLabel(resultCount, totalMatching);
      if (clearBtn) clearBtn.hidden = pins === 0;

      draftPreviewCount = countShownOnly(filt.draftSel, filt.draftCat);

      syncOpenBadge();
      renderActiveRemovalChips();
      updateEmptyLead(totalMatching, pins);
      catalogUrl.syncCommittedToLocation();

      syncApplyFooterText();

      const chipSource = filtersDrawerState.isOpen && isMobileFiltersLayout() ? filt.draftSel : filt.committedSel;
      const chipCatUnused =
        filtersDrawerState.isOpen && isMobileFiltersLayout()
          ? filt.draftCat
          : filt.committedCat;
      syncChipUi(chipSource, chipCatUnused);

      notifySubscribers("commit", { pins, primaryShown: resultCount, totalMatching, resultCount });
    }

    function toggleChipAcrossModes(chip) {
      const group = chip.dataset.group;
      const value = chip.dataset.value;
      if (!group || !value) return;

      const normalizedValues = normalizeSelectedFilterValues(group, value, chip.textContent);
      if (!normalizedValues.length) return;

      const fullyActiveBefore = normalizedValues.every((normalized) =>
        normalized ? pickWorkingSets().selected[group].has(normalized) : false
      );
      const nextActive = !fullyActiveBefore;

      const { selected, isDraftFlow } = pickWorkingSets();
      if (!selected[group]) return;

      toggleTokensInSelection(selected, group, normalizedValues, nextActive, !isDraftFlow, false);

      const chipSel = filtersDrawerState.isOpen && isMobileFiltersLayout() ? filt.draftSel : filt.committedSel;
      const chipCatUnused =
        filtersDrawerState.isOpen && isMobileFiltersLayout()
          ? filt.draftCat
          : filt.committedCat;
      syncChipUi(chipSel, chipCatUnused);

      if (!isDraftFlow) {
        applyCommittedToDom();
        return;
      }

      draftPreviewCount = countShownOnly(filt.draftSel, filt.draftCat);
      syncApplyFooterText();
    }

    function clearSelectionGroups(selection, groups, trackRecentClear) {
      (groups || FILTER_GROUPS).forEach((group) => {
        if (!selection[group]) return;
        [...selection[group]].forEach((token) => {
          selection[group].delete(token);
          if (trackRecentClear !== false) syncRecentRemoval(group, token, false);
        });
      });
    }

    function resetModalDraftOnly() {
      clearSelectionGroups(filt.draftSel, FILTER_GROUPS, true);
      filt.draftCat = null;
      draftPreviewCount = countShownOnly(filt.draftSel, filt.draftCat);
      syncChipUi(filt.draftSel, filt.draftCat);
      syncApplyFooterText();
    }

    function setCatalogCategory(slug) {
      const nextSlug = slug && String(slug).trim() ? String(slug).trim() : null;
      if (pickWorkingSets().isDraftFlow) {
        filt.draftCat = nextSlug;
        draftPreviewCount = countShownOnly(filt.draftSel, filt.draftCat);
        syncChipUi(filt.draftSel, filt.draftCat);
        syncApplyFooterText();
        return;
      }

      filt.committedCat = nextSlug;
      if (nextSlug) pushRecent("catalog", nextSlug);
      else recentStack = recentStack.filter((item) => item.group !== "catalog");
      rollbackDraftFromCommitted();
      applyCommittedToDom();
    }

    function setGroupValues(group, values) {
      if (!filt.committedSel[group]) return;
      filt.committedSel[group].clear();
      (values || []).forEach((value) => {
        normalizeSelectedFilterValues(group, value, "").forEach((token) => {
          if (token && filt.committedSel[group]) toggleTokensInSelection(filt.committedSel, group, [token], true, true, false);
        });
      });

      rollbackDraftFromCommitted();
      applyCommittedToDom();
    }

    function clearGroups(groups) {
      clearSelectionGroups(filt.committedSel, groups || FILTER_GROUPS, true);
      if (!groups || groups === FILTER_GROUPS) {
        filt.committedCat = null;
        filt.committedNameQuery = "";
        filt.draftNameQuery = "";
        syncNameSearchInputs("");
        clearRecentFully();
      }
      rollbackDraftFromCommitted();
      applyCommittedToDom();
    }

    /** Один метод для верхнего поиска: перезаписывает указанные группы и один раз применяет каталог. */
    function applyPatch(patch) {
      const {
        city = [],
        distance = [],
        beach = [],
        price = [],
        room = [],
        name,
      } = patch || {};

      const batch = [
        ["city", city],
        ["distance", distance],
        ["beach", beach],
        ["price", price],
        ["room", room],
      ];

      batch.forEach(([groupKey, vals]) => {
        if (!filt.committedSel[groupKey]) return;
        filt.committedSel[groupKey].clear();
        (vals || []).forEach((raw) => {
          normalizeSelectedFilterValues(groupKey, raw, "").forEach((token) => {
            if (token) toggleTokensInSelection(filt.committedSel, groupKey, [token], true, false, false);
          });
        });
      });

      if (name !== undefined) {
        filt.committedNameQuery = String(name || "").trim();
        filt.draftNameQuery = filt.committedNameQuery;
        syncNameSearchInputs(filt.committedNameQuery);
      }

      rebuildRecentStackFromSelections();
      rollbackDraftFromCommitted();
      syncChipUi(filt.committedSel, filt.committedCat);
      applyCommittedToDom();
    }

    function applySearchFromForm(patch) {
      applyPatch(patch);
    }

    function bindActiveRemovalDelegation() {
      activeFiltersList?.addEventListener("click", (event) => {
        const nameBtn = event.target.closest("[data-remove-name]");
        if (nameBtn) {
          setNameQuery("");
          return;
        }
        const categoryBtn = event.target.closest("[data-remove-category]");
        if (categoryBtn) {
          setCatalogCategory(null);
          return;
        }
        const tokenBtn = event.target.closest("[data-remove-group]");
        if (!tokenBtn || !tokenBtn.dataset.removeToken) return;

        const group = tokenBtn.getAttribute("data-remove-group") || "";
        const token = tokenBtn.getAttribute("data-remove-token") || "";
        if (!group || !token || !filt.committedSel[group]) return;

        normalizeSelectedFilterValues(group, token, "").forEach((norm) => {
          if (!norm || !filt.committedSel[group]) return;
          filt.committedSel[group].delete(norm);
          syncRecentRemoval(group, norm, false);
        });

        rollbackDraftFromCommitted();
        applyCommittedToDom();
      });
    }

    function removeLastCommittedFilterToken() {
      const last = popLastRecent();
      if (!last) return false;
      if (last.group === "catalog") {
        filt.committedCat = null;
      } else if (last.group === "name") {
        filt.committedNameQuery = "";
        filt.draftNameQuery = "";
        syncNameSearchInputs("");
      } else if (filt.committedSel[last.group]) {
        filt.committedSel[last.group].delete(last.token);
      }
      rollbackDraftFromCommitted();
      applyCommittedToDom();
      return true;
    }

    const { openFiltersModal, closeFiltersModal } = attachFiltersDrawerInteractions({
      state: filtersDrawerState,
      filt,
      filtersModal,
      body,
      mobileDraftHint,
      openFiltersBtn,
      isMobileFiltersLayout,
      rollbackDraftFromCommitted,
      syncChipUi,
      syncApplyFooterText,
      trackAnalytics,
      countShownDraft: (selected, slug) => countShownOnly(selected, slug),
      onDraftPreviewCount(n) {
        draftPreviewCount = n;
      },
    });

    function buildSelectionTitle() {
      const parts = [];
      FILTER_GROUPS.forEach((group) => {
        [...filt.committedSel[group]].forEach((token) => {
          const label = labelForToken(group, token);
          if (label) parts.push(label);
        });
      });
      if (filt.committedCat && CATALOG_CATEGORY_LABELS[filt.committedCat]) {
        parts.unshift(CATALOG_CATEGORY_LABELS[filt.committedCat]);
      }
      const nameQuery = String(filt.committedNameQuery || "").trim();
      if (nameQuery) parts.push(`«${nameQuery}»`);
      return parts.length ? parts.join(" · ") : "Подборка по параметрам";
    }

    const selectionPodborka = attachSelectionPodborkaView({
      grid,
      heroEl: selectionHero,
      viewEl: selectionView,
      titleEl: selectionTitle,
      countEl: selectionCount,
      shareBtn: shareSelectionBtn,
      shareHeroBtn: shareSelectionHeroBtn,
      editFiltersBtn: editSelectionFiltersBtn,
      openFiltersModal,
      buildSelectionTitle,
    });

    /** Привязка чипов, кнопок и модалки — после объявления всех обработчиков состояния. */
    function wireFilterUiInteractions() {
      chips.forEach((chip) => {
        chip.type = "button";
        chip.setAttribute("aria-pressed", "false");
        chip.addEventListener("click", () => toggleChipAcrossModes(chip));
      });

      clearBtn?.addEventListener("click", () => {
        catalogExpanded = false;
        clearSelectionGroups(filt.committedSel, FILTER_GROUPS, true);
        filt.committedCat = null;
        filt.committedNameQuery = "";
        filt.draftNameQuery = "";
        syncNameSearchInputs("");
        clearRecentFully();
        rollbackDraftFromCommitted();
        syncChipUi(filt.committedSel, filt.committedCat);
        applyCommittedToDom();
        trackAnalytics("clear_filters_catalog");
      });

      emptyResetBtn?.addEventListener("click", () => {
        clearBtn?.click();
      });

      emptyRemoveLastBtn?.addEventListener("click", () => {
        removeLastCommittedFilterToken();
      });

      openFiltersBtn?.addEventListener("click", () => openFiltersModal());

      closeFilterEls.forEach((element) => {
        element.addEventListener("click", () => closeFiltersModal({}));
      });

      applyFiltersBtn?.addEventListener("click", () => {
        if (!filtersModal?.classList.contains("is-visible")) return;
        if (isMobileFiltersLayout()) applyCommittedFromDraft();
        closeFiltersModal({ restoreCommittedDraft: false });
      });

      modalResetDraftBtn?.addEventListener("click", () => {
        const usingDraftFlow = filtersDrawerState.isOpen && isMobileFiltersLayout();
        if (!usingDraftFlow) {
          clearBtn?.click();
          return;
        }
        resetModalDraftOnly();
      });

      catalogExpandBtn?.addEventListener("click", () => {
        catalogExpanded = true;
        applyCommittedToDom();
        catalogExpandBtn.setAttribute("hidden", "");
      });

      document.addEventListener(
        "keydown",
        (event) => {
          if (event.key === "Escape" && filtersModal && !filtersModal.hidden) {
            event.preventDefault();
            closeFiltersModal({});
          }
        },
        false
      );

      bindActiveRemovalDelegation();

      window.addEventListener("popstate", () => {
        suppressUrlSync = true;
        catalogUrl.absorbLocationIntoCommitted();
        suppressUrlSync = false;
        rollbackDraftFromCommitted();
        rebuildRecentStackFromSelections();
        syncNameSearchInputs(filt.committedNameQuery);
        applyCommittedToDom();
      });
    }

    function bootstrapFiltersFromUrlAndDom() {
      if (!catalogMediaDeferred) {
        deferCatalogCardImages(getCards(), CATALOG_INITIAL_LIMIT);
        catalogMediaDeferred = true;
      }
      suppressUrlSync = true;
      catalogUrl.absorbLocationIntoCommitted();
      suppressUrlSync = false;
      if (!hasActiveCommittedFilters()) {
        applyInitialCatalogLimitWithoutIndex();
        return;
      }
      rebuildCardIndex();
      rollbackDraftFromCommitted();
      rebuildRecentStackFromSelections();
      syncNameSearchInputs(filt.committedNameQuery);
      applyCommittedToDom();
    }

    wireFilterUiInteractions();
    bootstrapFiltersFromUrlAndDom();

    return {
      refresh: () => {
        rebuildCardIndex();
        deferCatalogCardImages(getCards(), CATALOG_INITIAL_LIMIT);
        catalogMediaDeferred = true;
        applyCommittedToDom();
      },
      setCatalogCategory,
      setGroupValues,
      clearGroups,
      applySearchFromForm,
      applyPatch,
      setNameQuery,
      getNameQuery: () => filt.committedNameQuery,
      subscribe(listener) {
        return filt.subscribe(listener);
      },
      getCommittedSnapshot() {
        return filt.getCommittedSnapshot();
      },
    };
  }

  function initSearchBar(filtersController) {
    const form = document.getElementById("home-search-form");
    if (!form || !filtersController) return;

    const nameInput = document.getElementById("search-name");
    const catalogNameInput = document.getElementById("catalog-name-search");
    const citySelect = document.getElementById("search-city");
    const distanceSelect = document.getElementById("search-distance");
    const beachSelect = document.getElementById("search-beach");
    const priceSelect = document.getElementById("search-price");
    const guestsInput = document.getElementById("search-guests");

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

    if (nameInput) nameInput.value = filtersController.getNameQuery?.() || "";

    let nameDebounceTimer = null;
    catalogNameInput?.addEventListener("input", () => {
      clearTimeout(nameDebounceTimer);
      nameDebounceTimer = setTimeout(() => {
        const value = catalogNameInput.value.trim();
        if (nameInput && nameInput.value !== value) nameInput.value = value;
        filtersController.setNameQuery?.(value);
      }, 350);
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const name = nameInput?.value.trim() || "";
      const city = citySelect?.value || "";
      const distance = distanceSelect?.value || "";
      const beach = beachSelect?.value || "";
      const price = priceSelect?.value || "";
      const guestsValue = String(guestsInput?.value || "").trim();
      const room = guestsValue === "five-plus" ? ["five-plus"] : [];

      filtersController.applyPatch({
        name,
        city: city ? [city] : [],
        distance: distance ? [distance] : [],
        beach: beach ? [beach] : [],
        price: price ? [price] : [],
        room,
      });

      document.getElementById("catalog")?.scrollIntoView({ behavior: "smooth", block: "start" });
      trackAnalytics("home_search_submit", {
        name: name || null,
        city,
        distance,
        beach,
        price,
        guests: guestsValue || null,
      });
    });
  }

  function initHomeTopbarSticky() {
    const shell = document.querySelector(".site-concept.site-concept--home");
    const topbar = shell?.querySelector(":scope > .site-concept__topbar");
    const masthead = shell?.querySelector(":scope > .site-concept__masthead");
    if (!topbar || !masthead) return;

    topbar.classList.add("is-over-masthead");

    if (!("IntersectionObserver" in window)) {
      topbar.classList.remove("is-over-masthead");
      topbar.classList.add("is-sticky-scrolled");
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        const overBanner = Boolean(entry?.isIntersecting);
        topbar.classList.toggle("is-over-masthead", overBanner);
        topbar.classList.toggle("is-sticky-scrolled", !overBanner);
      },
      { rootMargin: "-12px 0px 0px 0px", threshold: [0, 0.05, 0.2] }
    );
    observer.observe(masthead);
  }

  function initHeroVideoQuality() {
    const video = document.querySelector(".site-concept__hero-video-player");
    if (!video) return;

    const inlineSrc = (video.getAttribute("src") || "").trim();
    const rawHigh = video.dataset.highSrc || "";
    const rawLow = video.dataset.lowSrc || "";
    let highSrc = rawHigh ? absolutizeKvartiraCoverUrl(rawHigh) || rawHigh : "";
    let lowSrc = rawLow ? absolutizeKvartiraCoverUrl(rawLow) || rawLow : "";
    if (!highSrc && inlineSrc) highSrc = inlineSrc;

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

    const shouldDefer = video.preload === "none" || video.dataset.deferLoad === "1";
    if (!shouldDefer) {
      applySrc(selectedSrc);
      return;
    }

    video.removeAttribute("src");
    video.dataset.pendingSrc = selectedSrc;
    let applied = false;

    const loadDeferredVideo = (playAfterLoad) => {
      if (applied) return;
      applied = true;
      applySrc(video.dataset.pendingSrc || selectedSrc);
      if (playAfterLoad) {
        const promise = video.play();
        if (promise && typeof promise.catch === "function") promise.catch(() => {});
      }
    };

    video.addEventListener("pointerdown", () => loadDeferredVideo(false), { once: true });
    video.addEventListener("touchstart", () => loadDeferredVideo(false), { once: true, passive: true });
    video.addEventListener("focus", () => loadDeferredVideo(false), { once: true });
    video.addEventListener("play", () => loadDeferredVideo(true), { once: true });
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

  const OBJECTS_MAP_CONSTRUCTOR_ID =
    "80408220233bb515383a3bc3da359eb235d60e8dd3dddfe843612590179aabd1";

  const CITY_MAP_GEO = {
    ldzaa: { label: "Лдзаа", short: "Лдзаа", lon: 40.32, lat: 43.05, z: 13 },
    pitsunda: { label: "Пицунда", short: "Пицунда", lon: 40.34, lat: 43.16, z: 13 },
    gagra: { label: "Гагра", short: "Гагра", lon: 40.265, lat: 43.278, z: 13 },
    alakhadzy: { label: "Алахадзы", short: "Алахадзы", lon: 40.28, lat: 43.22, z: 14 },
    gudauta: { label: "Гудаута", short: "Гудаута", lon: 40.62, lat: 43.1, z: 13 },
    "new-afon": { label: "Новый Афон", short: "Н. Афон", lon: 40.82, lat: 43.09, z: 13 },
    sukhum: { label: "Сухум", short: "Сухум", lon: 41.02, lat: 43.0, z: 12 },
    tsandripsh: { label: "Цандрипш", short: "Цандрипш", lon: 40.34, lat: 43.38, z: 13 },
  };

  const DEFAULT_CITY_MAP_GEO = { label: "Абхазия", short: "Абхазия", lon: 40.5, lat: 43.15, z: 10 };

  const CITY_TEXT_TO_KEY = [
    ["новый афон", "new-afon"],
    ["цандрипш", "tsandripsh"],
    ["алахадз", "alakhadzy"],
    ["гагрск", "gagra"],
    ["гагра", "gagra"],
    ["пицунд", "pitsunda"],
    ["гудаут", "gudauta"],
    ["лдзаа", "ldzaa"],
    ["сухум", "sukhum"],
  ];

  function cityGeo(cityKey) {
    return CITY_MAP_GEO[cityKey] || DEFAULT_CITY_MAP_GEO;
  }

  function buildObjectsMapPageUrl(cityKey) {
    const base = "/karta/";
    if (!cityKey) return base;
    return `${base}?city=${encodeURIComponent(cityKey)}`;
  }

  function primaryCityKeyFromFilters(filters) {
    const raw = filters?.city;
    const values = Array.isArray(raw)
      ? raw
      : String(raw || "")
          .split("|")
          .map((value) => value.trim())
          .filter(Boolean);
    return values[0] || "";
  }

  function primaryCityKeyFromCard(card) {
    if (!card) return "";
    const raw = card.getAttribute("data-filter-city") || "";
    return raw.split("|").map((value) => value.trim()).filter(Boolean)[0] || "";
  }

  function inferCityKeyFromText(text) {
    const normalized = String(text || "").toLowerCase();
    for (const [needle, key] of CITY_TEXT_TO_KEY) {
      if (normalized.includes(needle)) return key;
    }
    return "";
  }

  function ensureCatalogCardMediaWrap(card) {
    let mediaWrap = card.querySelector(".catalog-card__media-wrap");
    if (mediaWrap) return mediaWrap;
    const firstImage = card.querySelector("img");
    if (!firstImage) return null;
    mediaWrap = document.createElement("div");
    mediaWrap.className = "catalog-card__media-wrap";
    firstImage.parentNode?.insertBefore(mediaWrap, firstImage);
    mediaWrap.appendChild(firstImage);
    return mediaWrap;
  }

  function createCatalogMapPlaque(cityKey) {
    const geo = cityGeo(cityKey);
    const plaque = document.createElement("span");
    plaque.className = `catalog-card__map-plaque catalog-card__map-plaque--${cityKey || "default"}`;
    plaque.dataset.mapCity = cityKey || "";
    plaque.setAttribute("role", "link");
    plaque.setAttribute("tabindex", "0");

    const pin = document.createElement("span");
    pin.className = "catalog-card__map-plaque-pin";
    pin.setAttribute("aria-hidden", "true");

    const city = document.createElement("span");
    city.className = "catalog-card__map-plaque-city";
    city.textContent = geo.short || geo.label;

    const mapLabel = document.createElement("span");
    mapLabel.className = "catalog-card__map-plaque-map";
    mapLabel.setAttribute("aria-hidden", "true");
    mapLabel.textContent = "карта";

    plaque.append(pin, city, mapLabel);
    return plaque;
  }

  function wireCatalogMapPlaque(plaque) {
    const openMap = (event) => {
      event.preventDefault();
      event.stopPropagation();
      window.open(buildObjectsMapPageUrl(plaque.dataset.mapCity || ""), "_blank", "noopener,noreferrer");
    };
    plaque.addEventListener("click", openMap);
    plaque.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      openMap(event);
    });
  }

  function appendCatalogMapPlaque(card, cityKey) {
    if (!card || !cityKey || card.querySelector(".catalog-card__map-plaque")) return;
    const mediaWrap = ensureCatalogCardMediaWrap(card);
    if (!mediaWrap) return;
    const plaque = createCatalogMapPlaque(cityKey);
    wireCatalogMapPlaque(plaque);
    mediaWrap.appendChild(plaque);
  }

  function initCatalogMapPlaques(root = document) {
    if (!root?.querySelectorAll) return;
    root.querySelectorAll(".catalog-card").forEach((card) => {
      appendCatalogMapPlaque(card, primaryCityKeyFromCard(card));
      card.querySelectorAll(".catalog-card__map-plaque").forEach((plaque) => {
        if (plaque.dataset.mapWired === "1") return;
        plaque.dataset.mapWired = "1";
        wireCatalogMapPlaque(plaque);
      });
    });
  }

  function inferObjectPageCityKey(root) {
    const scope = root || document;
    return (
      inferCityKeyFromText(scope.querySelector(".location")?.textContent) ||
      inferCityKeyFromText(scope.querySelector(".hotel-card__rating-summary")?.textContent)
    );
  }

  function appendObjectPageMapPlaque(host, cityKey, variant) {
    if (!host || !cityKey || host.querySelector(`.object-card__map-plaque${variant ? `[data-map-variant="${variant}"]` : ""}`)) {
      return;
    }

    const plaque = createCatalogMapPlaque(cityKey);
    plaque.classList.add("object-card__map-plaque");
    if (variant) plaque.dataset.mapVariant = variant;
    if (variant === "header") {
      // Под названием объекта плашка превращается в текстовую кнопку карты.
      const cityEl = plaque.querySelector(".catalog-card__map-plaque-city");
      if (cityEl) cityEl.textContent = "Смотреть на карте";
      plaque.querySelector(".catalog-card__map-plaque-map")?.remove();
    }
    wireCatalogMapPlaque(plaque);
    host.appendChild(plaque);
  }

  function initObjectPageMapPlaque() {
    const root = document.querySelector(".hotel-site-concept");
    if (!root || root.dataset.mapPlaqueWired === "1") return;

    const cityKey = inferObjectPageCityKey(root);
    if (!cityKey) return;

    appendObjectPageMapPlaque(root.querySelector(".hotel-card__main-photo"), cityKey, "photo");

    const headerMain = root.querySelector(".hotel-card__header-main");
    if (headerMain) {
      let row = headerMain.querySelector(".object-card__map-plaque-row");
      if (!row) {
        row = document.createElement("div");
        row.className = "object-card__map-plaque-row";
        // Кнопка карты живёт ПОД названием объекта.
        const title = headerMain.querySelector("h1, h2");
        if (title) title.insertAdjacentElement("afterend", row);
        else headerMain.prepend(row);
      }
      appendObjectPageMapPlaque(row, cityKey, "header");
    }

    root.querySelector(".hotel-card__map-link")?.remove();
    root.dataset.mapPlaqueWired = "1";
  }

  function addHotelVideoBadges(grid) {
    if (!grid) return;
    grid.querySelectorAll('.catalog-card[data-has-video="1"]').forEach((card) => {
      let mediaWrap = card.querySelector(".catalog-card__media-wrap");
      if (!mediaWrap) {
        const firstImage = card.querySelector("img");
        if (firstImage) {
          mediaWrap = document.createElement("div");
          mediaWrap.className = "catalog-card__media-wrap";
          firstImage.parentNode?.insertBefore(mediaWrap, firstImage);
          mediaWrap.appendChild(firstImage);
        }
      }
      if (!mediaWrap || mediaWrap.querySelector(".catalog-card__badge")) return;

      const badge = document.createElement("span");
      badge.className = "catalog-card__badge";
      badge.textContent = "Видео";
      mediaWrap.prepend(badge);
    });
  }

  async function hydrateHomeCatalog(filtersController) {
    const grid = document.getElementById("catalog-grid");
    if (!grid) return;
    // Главная уже содержит полную сетку карточек из статической сборки (разметка с 📍 / 🏖 и <br>).
    // Повторная отрисовка из Supabase заменяет DOM и даёт «мигание»: сначала верстка из HTML/CSS,
    // затем упрощённые карточки из formatHotelCardSummary. Не перезаписываем готовую сетку.
    // Важно: режим «подборка по параметрам» переносит карточки из сетки в
    // #selection-podborka-view — пустая сетка ещё не значит, что каталога нет.
    if (grid.querySelector(".catalog-card") || document.querySelector("#selection-podborka-view .catalog-card")) {
      addHotelVideoBadges(grid);
      initCatalogMapPlaques(grid);
      return;
    }

    try {
      const rows = await fetchListings({ sourceKind: "hotel" });
      if (!rows.length) return;
      renderHotelCards(rows, grid);
      addHotelVideoBadges(grid);
      filtersController.refresh();
    } catch (error) {
      console.error("Не удалось загрузить каталог отелей из Supabase", error);
      filtersController.refresh();
    }
  }

  /** Slugs removed from UI (e.g. Telegram service posts, not real listings). */
  const KVARTIRA_EXCLUDED_SLUGS = new Set(["general-1409"]);

  async function hydrateKvartiraCatalog(_filtersController) {
    // Квартиры входят в общий #catalog-grid на главной; отдельной страницы каталога нет.
  }

  function initMobileReviewsPlacement() {
    const reviewsPanel = document.querySelector(".hotel-site-concept .reviews-panel");
    const priceSection = document.querySelector(".hotel-site-concept .hotel-price-section");
    if (!reviewsPanel || !priceSection) return;

    let placeholder = document.querySelector("[data-reviews-placeholder]");
    if (!placeholder) {
      placeholder = document.createElement("div");
      placeholder.hidden = true;
      placeholder.setAttribute("data-reviews-placeholder", "");
      reviewsPanel.parentNode?.insertBefore(placeholder, reviewsPanel);
    }

    const syncPlacement = () => {
      const isMobile = window.matchMedia("(max-width: 760px)").matches;
      if (isMobile) {
        if (reviewsPanel.previousElementSibling !== priceSection) {
          priceSection.insertAdjacentElement("afterend", reviewsPanel);
        }
        return;
      }

      if (placeholder.nextElementSibling !== reviewsPanel) {
        placeholder.insertAdjacentElement("afterend", reviewsPanel);
      }
    };

    syncPlacement();
    window.addEventListener("resize", syncPlacement, { passive: true });
  }

  async function hydrateHotelPage() {
    const hotelRoot = document.querySelector(".hotel-page-v2");
    if (!hotelRoot && !/^\/hotels\/[^/]+\/?$/.test(window.location.pathname)) return;

    const match = window.location.pathname.match(/^\/hotels\/([^/]+)\/?$/);
    if (!match) {
      renderHotelReviews();
      return;
    }

    try {
      const row = await fetchListingBySlug(match[1]);
      if (!row) {
        renderHotelReviews();
        return;
      }

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

      renderHotelReviews(row);
    } catch (error) {
      console.error("Не удалось обновить страницу объекта из Supabase", error);
      renderHotelReviews();
    }
  }

  closeButton?.addEventListener("click", closeLightbox);
  prevButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    stepGalleryLightbox(-1);
  });
  nextButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    stepGalleryLightbox(1);
  });
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) closeLightbox();
  });

  lightbox.addEventListener(
    "touchstart",
    (event) => {
      galleryTouchStartX = event.changedTouches?.[0]?.clientX || 0;
    },
    { passive: true }
  );

  lightbox.addEventListener("touchend", (event) => {
    const endX = event.changedTouches?.[0]?.clientX || 0;
    const delta = endX - galleryTouchStartX;
    if (Math.abs(delta) < 40) return;
    stepGalleryLightbox(delta > 0 ? -1 : 1);
  });

  document.addEventListener("keydown", (event) => {
    if (lightbox.hasAttribute("hidden")) return;
    if (event.key === "Escape") closeLightbox();
    if (event.key === "ArrowLeft") stepGalleryLightbox(-1);
    if (event.key === "ArrowRight") stepGalleryLightbox(1);
  });

  document.addEventListener("click", (event) => {
    const cardGalleryHit = event.target.closest(
      ".hotel-card__gallery img, .hotel-card__gallery video.local-video, .hotel-card__main-photo, .hotel-card__thumbs"
    );
    if (cardGalleryHit) {
      event.preventDefault();
      const cardVideo =
        event.target.closest(".hotel-card__gallery video.local-video") ||
        cardGalleryHit.querySelector("video.local-video");
      if (cardVideo) {
        if (isVideoControlsClick(cardVideo, event)) return;
        event.preventDefault();
        openInlineGalleryVideoLightbox(cardVideo);
        return;
      }

      const cardImage =
        event.target.closest(".hotel-card__gallery img") ||
        (cardGalleryHit.matches("img") ? cardGalleryHit : cardGalleryHit.querySelector("img"));
      if (cardImage) {
        openGalleryLightboxAtKey(normalizeGallerySrc(gallerySrcFromImage(cardImage)));
      } else {
        openGalleryLightbox(0);
      }
      return;
    }

    const image = event.target.closest(
      ".media-grid img, .hotel-media-section img, .comment-media-grid img, .comment-review-grid img, .blog-article__media-gallery img"
    );
    if (image) {
      if (image.classList.contains("local-video-preview")) {
        const block = image.closest(".video-embed");
        const video = block?.querySelector("video.local-video");
        const src =
          video?.querySelector("source")?.getAttribute("src") ||
          video?.getAttribute("src") ||
          block?.querySelector(".video-link")?.href ||
          gallerySrcFromImage(image);
        if (src) {
          openGalleryLightboxAtKey(normalizeGallerySrc(src));
          return;
        }
        const link = block?.querySelector(".video-link");
        if (link?.href) window.open(link.href, "_blank", "noopener,noreferrer");
        return;
      }

      image.classList.add("media-grid__zoomable");
      openLightbox(gallerySrcFromImage(image), image.alt);
      return;
    }

    const video = event.target.closest(
      ".media-grid video.local-video, .hotel-media-section video.local-video, .comment-media-grid video.local-video, .comment-review-grid video.local-video, .blog-article__media-gallery video"
    );
    if (!video) return;
    if (isVideoControlsClick(video, event)) return;
    event.preventDefault();
    openInlineGalleryVideoLightbox(video);
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
      text.textContent = cleanReviewTextForDisplay(review.text || "");
    wrap.append(head, text);
    return wrap;
  }

  function normalizeGuestReviewKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function uniqueGuestReviews(list) {
    const usedHeads = new Set();
    const usedTexts = new Set();
    return (Array.isArray(list) ? list : []).filter((review) => {
      const head = normalizeGuestReviewKey(review?.head);
      const text = normalizeGuestReviewKey(review?.text);
      if (!head || !text || usedHeads.has(head) || usedTexts.has(text)) return false;
      usedHeads.add(head);
      usedTexts.add(text);
      return true;
    });
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
    list = uniqueGuestReviews(list);
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

  function initInPageAnchorFix() {
    /* content-visibility на карточках каталога делает высоту свёрнутых карточек
       приблизительной — прыжок к якорю ниже каталога промахивается. Докручиваем. */
    function correctScroll(hash) {
      const id = decodeURIComponent(String(hash || "").replace(/^#/, ""));
      if (!id) return;
      const target = document.getElementById(id);
      if (!target) return;
      const scroll = () => target.scrollIntoView({ block: "start" });
      window.requestAnimationFrame(scroll);
      window.setTimeout(scroll, 250);
      window.setTimeout(scroll, 700);
    }
    document.addEventListener("click", (event) => {
      const link = event.target.closest ? event.target.closest('a[href^="#"]') : null;
      if (!link) return;
      correctScroll(link.getAttribute("href"));
    });
    window.addEventListener("load", () => correctScroll(window.location.hash), { once: true });
  }

  initInPageAnchorFix();
  initHomeTopbarSticky();
  initHeroVideoQuality();
  initLocalVideoPosters();
  initLocalVideoNaturalPlayback();
  initCatalogMapPlaques();
  initObjectPageMapPlaque();
  absolutizeHotelSiteConceptMedia();
  void initRandomGuestReviews();

  initLazyScreenshotReviews();
  initStableAnchorScroll();

  const filtersController = initFilters();
  initSearchBar(filtersController);
  initCategoryPicks(filtersController);
  hydrateHomeCatalog(filtersController);
  hydrateKvartiraCatalog(filtersController);
  hydrateHotelPage();
  initListingPageShareLink();
  void initSimilarListings();
  void initSimilarBlogPosts();
  initMobileReviewsPlacement();
})();
