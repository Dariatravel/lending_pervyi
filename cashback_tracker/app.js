const DATA_URL = "/api/data";

const state = {
  data: null,
  selectedMonth: null,
};

const monthStatus = document.querySelector("#monthStatus");
const categoryDirectory = document.querySelector("#categoryDirectory");
const categorySearchInput = document.querySelector("#categorySearchInput");
const categorySearchSuggestions = document.querySelector("#categorySearchSuggestions");
const categorySearchStatus = document.querySelector("#categorySearchStatus");
const bankOverviewStatus = document.querySelector("#bankOverviewStatus");
const bankOverviewList = document.querySelector("#bankOverviewList");
const emptyTemplate = document.querySelector("#emptyStateTemplate");

init().catch((error) => {
  console.error(error);
  categorySearchStatus.textContent = "Не удалось загрузить данные.";
  bankOverviewStatus.textContent = "Не удалось загрузить данные.";
});

async function init() {
  state.data = normalizeData(await fetchData());
  state.selectedMonth = pickInitialMonth(state.data);
  bindEvents();
  render();
}

function bindEvents() {
  categorySearchInput.addEventListener("input", render);
  categorySearchInput.addEventListener("focus", render);
  categorySearchInput.addEventListener("blur", () => {
    window.setTimeout(hideSearchSuggestions, 120);
  });
  categorySearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideSearchSuggestions();
    }
  });
  categorySearchSuggestions.addEventListener("click", (event) => {
    const button = event.target.closest(".search-suggestion");
    if (!button) {
      return;
    }
    categorySearchInput.value = button.dataset.category || "";
    hideSearchSuggestions();
    render();
    categorySearchInput.focus();
  });
}

function render() {
  renderMonthStatus();
  renderBankOverview();
  renderCategoryDirectory();
}

function renderBankOverview() {
  const bankGroups = buildBankGroupsForMonth(state.selectedMonth);

  if (!bankGroups.length) {
    bankOverviewStatus.textContent = "Нет категорий за текущий месяц.";
    bankOverviewList.innerHTML = "";
    return;
  }

  const totalCategories = bankGroups.reduce((sum, group) => sum + group.categories.length, 0);
  bankOverviewStatus.textContent = `Банков: ${bankGroups.length}, категорий: ${totalCategories}.`;

  bankOverviewList.innerHTML = bankGroups
    .map(
      (group) => `
        <article class="bank-overview-item">
          <div class="bank-overview-bank">${escapeHtml(group.bankName)}</div>
          <ul class="bank-overview-categories">
            ${group.categories
              .map(
                (category) => `
                  <li>${escapeHtml(formatBankCategory(category))}</li>
                `,
              )
              .join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function renderMonthStatus() {
  const monthKey = state.selectedMonth;
  if (!monthKey) {
    monthStatus.textContent = "Нет данных за текущий месяц.";
    return;
  }

  const monthData = ensureMonth(monthKey);
  const offers = Object.values(monthData.banks).reduce(
    (sum, bankData) => sum + bankData.categories.filter((category) => normalizeText(category.name)).length,
    0,
  );
  const banks = state.data.banks.filter((bank) => {
    const bankData = ensureBankMonthData(monthData, bank.id);
    return bankData.categories.some((category) => normalizeText(category.name));
  }).length;

  monthStatus.textContent = `${formatMonth(monthKey)}: банков ${banks}, категорий ${offers}.`;
}

function renderCategoryDirectory() {
  const groups = buildCategoryGroupsForMonth(state.selectedMonth);
  const query = categorySearchInput.value.trim();
  const filteredGroups = filterCategoryGroups(groups, query);
  renderSearchSuggestions(groups, query);

  if (!groups.length) {
    categorySearchStatus.textContent = "За текущий месяц кешбек еще не добавлен.";
    categoryDirectory.innerHTML = "";
    categoryDirectory.append(emptyTemplate.content.cloneNode(true));
    return;
  }

  if (!filteredGroups.length) {
    categorySearchStatus.textContent = `По запросу "${query}" ничего не найдено.`;
    categoryDirectory.innerHTML = `
      <div class="empty-state">
        <h2>Ничего не найдено</h2>
        <p>Ищи по категории, бренду или банку. Показываются только категории из кешбека этого месяца.</p>
      </div>
    `;
    return;
  }

  const totalOffers = filteredGroups.reduce((sum, group) => sum + group.offers.length, 0);
  categorySearchStatus.textContent = query
    ? `Найдено категорий: ${filteredGroups.length}, предложений: ${totalOffers}.`
    : `Категорий в этом месяце: ${filteredGroups.length}, предложений: ${totalOffers}.`;

  categoryDirectory.innerHTML = filteredGroups
    .map(
      (group) => `
        <article class="category-card">
          <h2>${escapeHtml(group.category)}</h2>
          <p class="category-meta">Банков с кешбеком: ${group.offers.length}</p>
          <div class="category-offer-list">
            ${group.offers
              .map(
                (offer) => `
                  <div class="category-offer">
                    <div class="category-offer-top">
                      <div>
                        <div class="category-offer-bank">${escapeHtml(offer.bankName)}</div>
                        ${
                          offer.label
                            ? `<div class="category-offer-name">${escapeHtml(offer.label)}</div>`
                            : ""
                        }
                      </div>
                      <div class="category-offer-rate">${formatRate(offer.rate)}</div>
                    </div>
                    ${
                      offer.limit
                        ? `<div class="category-offer-limit">Лимит: ${escapeHtml(offer.limit)}</div>`
                        : ""
                    }
                    ${
                      offer.note
                        ? `<div class="category-offer-note">${escapeHtml(offer.note)}</div>`
                        : ""
                    }
                  </div>
                `,
              )
              .join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderSearchSuggestions(groups, query) {
  const focused = document.activeElement === categorySearchInput;
  if (!focused || !groups.length) {
    hideSearchSuggestions();
    return;
  }

  const categoryNames = groups.map((group) => group.category);
  const matchedNames = (query
    ? categoryNames.filter((name) => matchesSearch(name, query))
    : categoryNames
  ).slice(0, 12);

  if (!matchedNames.length) {
    hideSearchSuggestions();
    return;
  }

  categorySearchSuggestions.innerHTML = "";
  for (const categoryName of matchedNames) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-suggestion";
    button.dataset.category = categoryName;
    button.textContent = categoryName;
    categorySearchSuggestions.append(button);
  }

  categorySearchSuggestions.hidden = false;
}

function hideSearchSuggestions() {
  categorySearchSuggestions.hidden = true;
  categorySearchSuggestions.innerHTML = "";
}

function buildCategoryGroupsForMonth(monthKey) {
  if (!monthKey) {
    return [];
  }

  const monthData = ensureMonth(monthKey);
  const groups = new Map();

  for (const bank of state.data.banks) {
    const bankData = ensureBankMonthData(monthData, bank.id);
    for (const category of bankData.categories) {
      const rawName = String(category.name || "").trim();
      if (!rawName) {
        continue;
      }

      const { topCategory, offerName } = splitCategoryName(rawName);
      const normalizedTopCategory = normalizeTopCategory(topCategory);
      if (!groups.has(normalizedTopCategory)) {
        groups.set(normalizedTopCategory, []);
      }

      groups.get(normalizedTopCategory).push({
        bankName: bank.name,
        label: offerName,
        rate: Number(category.rate || 0),
        limit: String(category.limit || "").trim(),
        note: String(category.note || "").trim(),
        rawName,
      });
    }
  }

  return Array.from(groups.entries())
    .map(([category, offers]) => ({
      category,
      offers: offers.sort(
        (left, right) =>
          right.rate - left.rate ||
          left.bankName.localeCompare(right.bankName, "ru") ||
          left.label.localeCompare(right.label, "ru"),
      ),
    }))
    .sort((left, right) => left.category.localeCompare(right.category, "ru"));
}

function buildBankGroupsForMonth(monthKey) {
  if (!monthKey) {
    return [];
  }

  const monthData = ensureMonth(monthKey);
  const groups = [];

  for (const bank of state.data.banks) {
    const bankData = ensureBankMonthData(monthData, bank.id);
    const categories = bankData.categories
      .map((category) => {
        const rawName = String(category.name || "").trim();
        if (!rawName) {
          return null;
        }

        const { topCategory } = splitCategoryName(rawName);
        return {
          name: normalizeTopCategory(topCategory),
          rate: Number(category.rate || 0),
          limit: String(category.limit || "").trim(),
        };
      })
      .filter(Boolean)
      .sort(
        (left, right) =>
          right.rate - left.rate || left.name.localeCompare(right.name, "ru"),
      );

    if (!categories.length) {
      continue;
    }

    groups.push({
      bankName: bank.name,
      categories,
    });
  }

  return groups.sort((left, right) => left.bankName.localeCompare(right.bankName, "ru"));
}

function filterCategoryGroups(groups, query) {
  if (!query) {
    return groups;
  }

  return groups
    .map((group) => {
      const groupMatches = matchesSearch(group.category, query);
      const offers = groupMatches
        ? group.offers
        : group.offers.filter((offer) =>
            matchesSearch(
              [offer.bankName, offer.label, offer.limit, offer.note, offer.rawName]
                .filter(Boolean)
                .join(" "),
              query,
            ),
          );

      return { ...group, offers };
    })
    .filter((group) => group.offers.length > 0);
}

async function fetchData() {
  const response = await fetch(DATA_URL);
  if (!response.ok) {
    throw new Error("Не удалось получить данные");
  }
  return response.json();
}

function normalizeData(raw) {
  const banks = Array.isArray(raw?.banks) ? raw.banks : [];
  const months = raw?.months && typeof raw.months === "object" ? raw.months : {};

  return {
    version: 1,
    banks: banks
      .filter((bank) => bank && typeof bank === "object")
      .map((bank) => ({
        id: String(bank.id || createId("bank")),
        name: String(bank.name || "Без названия").trim(),
      })),
    months: Object.fromEntries(
      Object.entries(months).map(([monthKey, monthData]) => [
        monthKey,
        {
          banks: Object.fromEntries(
            Object.entries(monthData?.banks || {}).map(([bankId, bankData]) => [
              bankId,
              {
                categories: Array.isArray(bankData?.categories)
                  ? bankData.categories.map((category) => ({
                      id: String(category.id || createId("category")),
                      name: String(category.name || ""),
                      rate: parseRate(category.rate),
                      limit: String(category.limit || ""),
                      note: String(category.note || ""),
                    }))
                  : [],
              },
            ]),
          ),
        },
      ]),
    ),
  };
}

function pickInitialMonth(data) {
  const currentMonth = getCurrentMonth();
  if (data.months[currentMonth]) {
    return currentMonth;
  }

  const monthKeys = Object.keys(data.months).sort();
  return monthKeys.at(-1) || currentMonth;
}

function ensureMonth(monthKey) {
  if (!state.data.months[monthKey]) {
    state.data.months[monthKey] = { banks: {} };
  }
  return state.data.months[monthKey];
}

function ensureBankMonthData(monthData, bankId) {
  if (!monthData.banks[bankId]) {
    monthData.banks[bankId] = { categories: [] };
  }
  return monthData.banks[bankId];
}

function splitCategoryName(value) {
  const parts = value.split(" / ").map((part) => part.trim()).filter(Boolean);
  if (parts.length >= 2) {
    return {
      topCategory: parts[0],
      offerName: parts.slice(1).join(" / "),
    };
  }

  return {
    topCategory: value,
    offerName: "",
  };
}

function normalizeTopCategory(value) {
  const source = String(value || "").trim();
  const normalized = source.toLocaleLowerCase("ru-RU").replaceAll("ё", "е");

  if (normalized === "все покупки" || normalized === "за все покупки") {
    return "Все покупки";
  }

  if (normalized === "рестораны" || normalized === "кафе и рестораны") {
    return "Кафе и рестораны";
  }

  return source;
}

function matchesSearch(text, query) {
  const queryTokens = normalizeSearchTokens(query);
  if (!queryTokens.length) {
    return true;
  }

  const textTokens = normalizeSearchTokens(text);
  if (!textTokens.length) {
    return false;
  }

  return queryTokens.every((queryToken) =>
    textTokens.some(
      (textToken) =>
        textToken === queryToken ||
        textToken.startsWith(queryToken) ||
        queryToken.startsWith(textToken),
    ),
  );
}

function normalizeSearchTokens(value) {
  return String(value || "")
    .toLocaleLowerCase("ru-RU")
    .replaceAll("ё", "е")
    .replace(/[^a-zа-я0-9+]+/gi, " ")
    .split(" ")
    .map((token) => token.trim())
    .filter(Boolean)
    .map(stemToken);
}

function stemToken(token) {
  if (token.length <= 4) {
    return token;
  }

  return token.replace(/(иями|ями|ами|иях|ях|ах|ого|ему|ому|ыми|ими|ой|ий|ый|ая|яя|ое|ее|ие|ые|ов|ев|ам|ям|ом|ем|ах|ях|ы|и|а|я|е|о|у|ю|ь)$/u, "");
}

function parseRate(value) {
  const normalized = String(value ?? "")
    .replace("%", "")
    .replace(",", ".")
    .trim();
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function createId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function getCurrentMonth() {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  return `${today.getFullYear()}-${month}`;
}

function formatMonth(monthKey) {
  const [year, month] = monthKey.split("-").map(Number);
  return new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, 1));
}

function formatRate(rate) {
  return `${Number(rate).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

function formatBankCategory(category) {
  const base = `${category.name} - ${formatRate(category.rate)}`;
  if (!category.limit) {
    return base;
  }
  return `${base}, лимит: ${category.limit}`;
}

function normalizeText(value) {
  return String(value || "").trim().toLocaleLowerCase("ru-RU");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
