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
  const SCREENSHOT_REVIEW_BANK_URL = "/media/reviews/review_text_bank.json";
  const FILTER_GROUPS = ["distance", "food", "price", "city", "beach", "room", "stay"];
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
  let supabaseClientPromise = null;
  let screenshotReviewBank = null;
  let screenshotReviewBankPromise = null;

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
    const text = sentence(entry.text || "");
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

    return { global, by_object: byObject };
  }

  async function loadScreenshotReviewBank() {
    if (screenshotReviewBank) return screenshotReviewBank;
    if (screenshotReviewBankPromise) return screenshotReviewBankPromise;

    screenshotReviewBankPromise = fetch(SCREENSHOT_REVIEW_BANK_URL, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Не удалось загрузить ${SCREENSHOT_REVIEW_BANK_URL}: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        screenshotReviewBank = sanitizeBankPayload(payload);
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

  function getObjectReviewPool(slug) {
    const cleanSlug = String(slug || "").trim();
    if (!cleanSlug) return [];
    const byObject = screenshotReviewBank?.by_object || {};
    return Array.isArray(byObject[cleanSlug]) ? byObject[cleanSlug] : [];
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
    const scrollers = Array.from(document.querySelectorAll(".reviews-scroller"));
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
    const scrollers = Array.from(document.querySelectorAll(".reviews-scroller"));
    if (!scrollers.length) return;

    const context = extractObjectReviewContext(row);
    const objectPool = getObjectReviewPool(context.slug);
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
    /* Главное фото страницы объекта — то же, что в карточке на сайте (галерея photo-01…). */
    if (row.slug) {
      push(`/media/kvartira/${row.slug}/photo-01.jpg`);
      push(`/media/kvartira/${row.slug}/photo-02.jpg`);
    }
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
      return normalizeCardFilterValues(group, raw, card);
    }

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

    function isSelectedChip(group, value, chipText) {
      if (!group || !selected[group]) return false;
      const normalizedValues = normalizeSelectedFilterValues(group, value, chipText);
      if (!normalizedValues.length) return false;
      return normalizedValues.some((normalized) => selected[group].has(normalized));
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
        const active = Boolean(group && value && isSelectedChip(group, value, chip.textContent));
        chip.classList.toggle("is-active", active);
        chip.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function setGroupValues(group, values) {
      if (!selected[group]) return;
      selected[group].clear();
      (values || []).forEach((value) => {
        const normalizedValues = normalizeSelectedFilterValues(group, value, "");
        normalizedValues.forEach((normalized) => {
          if (normalized) selected[group].add(normalized);
        });
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

        const normalizedValues = normalizeSelectedFilterValues(group, value, chip.textContent);
        if (!normalizedValues.length) return;
        const currentlyActive = normalizedValues.every((normalized) => selected[group].has(normalized));

        if (currentlyActive) {
          normalizedValues.forEach((normalized) => selected[group].delete(normalized));
        } else {
          normalizedValues.forEach((normalized) => {
            if (normalized) selected[group].add(normalized);
          });
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
    if (grid.querySelector(".catalog-card")) {
      filtersController.refresh();
      return;
    }

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
    if (grid.querySelector(".catalog-card")) return;

    // Как и с основным каталогом: если карточки уже отрисованы статикой,
    // не перезатираем DOM данными из Supabase (иначе виден "мигающий" откат верстки/текста).
    if (grid.querySelector(".catalog-card")) return;

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

  loadScreenshotReviewBank().then(() => {
    renderReviewsForCurrentPage();
  });

  const filtersController = initFilters();
  initSearchBar(filtersController);
  initCategoryPicks(filtersController);
  hydrateHomeCatalog(filtersController);
  hydrateKvartiraCatalog();
  hydrateHotelPage();
})();
