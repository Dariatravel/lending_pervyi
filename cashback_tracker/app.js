const DATA_URL = "/api/data";

const state = {
  data: null,
  selectedMonth: getCurrentMonth(),
  saveTimeout: null,
};

const monthInput = document.querySelector("#monthInput");
const saveStatus = document.querySelector("#saveStatus");
const monthStatus = document.querySelector("#monthStatus");
const bankList = document.querySelector("#bankList");
const banksGrid = document.querySelector("#banksGrid");
const summaryTableWrap = document.querySelector("#summaryTableWrap");
const categoryDirectory = document.querySelector("#categoryDirectory");
const categorySearchInput = document.querySelector("#categorySearchInput");
const categorySearchStatus = document.querySelector("#categorySearchStatus");
const addBankForm = document.querySelector("#addBankForm");
const bankNameInput = document.querySelector("#bankNameInput");
const bulkInput = document.querySelector("#bulkInput");
const bulkImportBtn = document.querySelector("#bulkImportBtn");
const copyPrevBtn = document.querySelector("#copyPrevBtn");
const exportBtn = document.querySelector("#exportBtn");
const importInput = document.querySelector("#importInput");
const emptyTemplate = document.querySelector("#emptyStateTemplate");

init().catch((error) => {
  console.error(error);
  setSaveStatus("Не удалось загрузить данные", "error");
});

async function init() {
  monthInput.value = state.selectedMonth;
  state.data = normalizeData(await fetchData());
  render();
  bindEvents();
}

function bindEvents() {
  monthInput.addEventListener("change", () => {
    state.selectedMonth = monthInput.value || getCurrentMonth();
    ensureMonth(state.selectedMonth);
    render();
  });

  categorySearchInput.addEventListener("input", () => {
    renderCategoryDirectory();
  });

  addBankForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = bankNameInput.value.trim();
    if (!name) {
      return;
    }

    state.data.banks.push({
      id: createId("bank"),
      name,
    });

    bankNameInput.value = "";
    await persistAndRender("Банк добавлен");
  });

  bulkImportBtn.addEventListener("click", async () => {
    const lines = bulkInput.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (!lines.length) {
      window.alert("Добавьте хотя бы одну строку для импорта.");
      return;
    }

    const monthData = ensureMonth(state.selectedMonth);
    let importedCount = 0;

    for (const line of lines) {
      const [bankName, categoryName, rateRaw, limit = "", note = ""] = line
        .split("|")
        .map((part) => part.trim());

      if (!bankName || !categoryName || !rateRaw) {
        continue;
      }

      const bank = findOrCreateBank(bankName);
      const bankData = ensureBankMonthData(monthData, bank.id);
      const normalizedName = normalizeText(categoryName);
      const existing = bankData.categories.find(
        (category) => normalizeText(category.name) === normalizedName,
      );
      const nextCategory = {
        id: existing?.id || createId("category"),
        name: categoryName,
        rate: parseRate(rateRaw),
        limit,
        note,
      };

      if (existing) {
        Object.assign(existing, nextCategory);
      } else {
        bankData.categories.push(nextCategory);
      }

      importedCount += 1;
    }

    bulkInput.value = "";
    await persistAndRender(`Импортировано строк: ${importedCount}`);
  });

  copyPrevBtn.addEventListener("click", async () => {
    const previousMonthKey = getPreviousMonth(state.selectedMonth);
    const previousMonth = state.data.months[previousMonthKey];

    if (!previousMonth) {
      window.alert("Для предыдущего месяца данных нет.");
      return;
    }

    const currentMonth = ensureMonth(state.selectedMonth);
    const hasExistingData = Object.values(currentMonth.banks).some(
      (bankData) => bankData.categories.length > 0,
    );

    if (
      hasExistingData &&
      !window.confirm("В выбранном месяце уже есть данные. Перезаписать копией?")
    ) {
      return;
    }

    state.data.months[state.selectedMonth] = deepClone(previousMonth);
    await persistAndRender(`Данные скопированы из ${formatMonth(previousMonthKey)}`);
  });

  exportBtn.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(state.data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `cashback-data-${state.selectedMonth}.json`;
    link.click();
    URL.revokeObjectURL(url);
  });

  importInput.addEventListener("change", async (event) => {
    const [file] = event.target.files || [];
    if (!file) {
      return;
    }

    try {
      const content = await file.text();
      state.data = normalizeData(JSON.parse(content));
      await saveData(state.data);
      render();
      setSaveStatus("JSON импортирован", "idle");
    } catch (error) {
      console.error(error);
      setSaveStatus("Ошибка импорта JSON", "error");
    } finally {
      importInput.value = "";
    }
  });

  bankList.addEventListener("click", async (event) => {
    const removeButton = event.target.closest("[data-remove-bank]");
    if (!removeButton) {
      return;
    }

    const bankId = removeButton.dataset.removeBank;
    const bank = state.data.banks.find((item) => item.id === bankId);
    if (!bank) {
      return;
    }

    const confirmed = window.confirm(
      `Удалить банк "${bank.name}" из списка и всех месяцев?`,
    );
    if (!confirmed) {
      return;
    }

    state.data.banks = state.data.banks.filter((item) => item.id !== bankId);
    for (const month of Object.values(state.data.months)) {
      delete month.banks[bankId];
    }
    await persistAndRender("Банк удален");
  });

  if (banksGrid) {
    banksGrid.addEventListener("click", async (event) => {
      const addCategoryButton = event.target.closest("[data-add-category]");
      if (addCategoryButton) {
        const bankId = addCategoryButton.dataset.addCategory;
        const bankData = ensureBankMonthData(ensureMonth(state.selectedMonth), bankId);
        bankData.categories.push({
          id: createId("category"),
          name: "",
          rate: 0,
          limit: "",
          note: "",
        });
        await persistAndRender("Категория добавлена");
        return;
      }

      const clearMonthButton = event.target.closest("[data-clear-month]");
      if (clearMonthButton) {
        const bankId = clearMonthButton.dataset.clearMonth;
        const bank = state.data.banks.find((item) => item.id === bankId);
        if (!bank) {
          return;
        }

        if (
          !window.confirm(`Очистить данные за ${formatMonth(state.selectedMonth)} для "${bank.name}"?`)
        ) {
          return;
        }

        ensureBankMonthData(ensureMonth(state.selectedMonth), bankId).categories = [];
        await persistAndRender("Данные банка за месяц очищены");
        return;
      }

      const deleteCategoryButton = event.target.closest("[data-delete-category]");
      if (deleteCategoryButton) {
        const { bankId, categoryId } = deleteCategoryButton.dataset;
        const bankData = ensureBankMonthData(ensureMonth(state.selectedMonth), bankId);
        bankData.categories = bankData.categories.filter((item) => item.id !== categoryId);
        await persistAndRender("Категория удалена");
      }
    });

    banksGrid.addEventListener("input", (event) => {
      const input = event.target.closest("[data-field]");
      if (!input) {
        return;
      }

      const { bankId, categoryId, field } = input.dataset;
      const bankData = ensureBankMonthData(ensureMonth(state.selectedMonth), bankId);
      const category = bankData.categories.find((item) => item.id === categoryId);
      if (!category) {
        return;
      }

      category[field] = field === "rate" ? parseRate(input.value) : input.value;
      scheduleSave();
      renderSummary();
      renderCategoryDirectory();
      renderMonthStatus();
    });
  }
}

function render() {
  ensureMonth(state.selectedMonth);
  renderBankList();
  renderBanksGrid();
  renderSummary();
  renderCategoryDirectory();
  renderMonthStatus();
}

function renderBankList() {
  if (!state.data.banks.length) {
    bankList.innerHTML = "";
    bankList.append(emptyTemplate.content.cloneNode(true));
    return;
  }

  bankList.innerHTML = state.data.banks
    .map((bank) => {
      const monthData = ensureBankMonthData(ensureMonth(state.selectedMonth), bank.id);
      return `
        <div class="bank-chip">
          <strong>${escapeHtml(bank.name)}</strong>
          <span class="chip-meta">${monthData.categories.length} категорий за ${escapeHtml(
            formatMonth(state.selectedMonth),
          )}</span>
          <button class="danger-button ghost-button" data-remove-bank="${bank.id}" type="button">
            Удалить
          </button>
        </div>
      `;
    })
    .join("");
}

function renderBanksGrid() {
  if (!banksGrid) {
    return;
  }

  if (!state.data.banks.length) {
    banksGrid.innerHTML = "";
    banksGrid.append(emptyTemplate.content.cloneNode(true));
    return;
  }

  banksGrid.innerHTML = state.data.banks
    .map((bank) => {
      const bankData = ensureBankMonthData(ensureMonth(state.selectedMonth), bank.id);
      const categoriesHtml = bankData.categories.length
        ? bankData.categories.map((category) => renderCategoryRow(bank.id, category)).join("")
        : `<div class="empty-card">Для этого банка пока нет категорий за ${escapeHtml(
            formatMonth(state.selectedMonth),
          )}.</div>`;

      return `
        <article class="bank-card">
          <div class="bank-card-header">
            <div>
              <p class="section-label">Банк</p>
              <h3>${escapeHtml(bank.name)}</h3>
            </div>
            <div class="bank-card-actions">
              <button class="small-button" data-add-category="${bank.id}" type="button">
                Добавить категорию
              </button>
              <button class="ghost-button" data-clear-month="${bank.id}" type="button">
                Очистить месяц
              </button>
            </div>
          </div>
          <div class="category-list">${categoriesHtml}</div>
        </article>
      `;
    })
    .join("");
}

function renderCategoryRow(bankId, category) {
  return `
    <div class="category-row">
      <div class="category-grid">
        <input
          type="text"
          value="${escapeAttribute(category.name)}"
          placeholder="Категория"
          data-bank-id="${bankId}"
          data-category-id="${category.id}"
          data-field="name"
        />
        <input
          type="number"
          step="0.1"
          min="0"
          value="${Number(category.rate || 0)}"
          placeholder="%"
          data-bank-id="${bankId}"
          data-category-id="${category.id}"
          data-field="rate"
        />
      </div>
      <div class="category-grid-secondary">
        <input
          type="text"
          value="${escapeAttribute(category.limit || "")}"
          placeholder="Лимит или условие"
          data-bank-id="${bankId}"
          data-category-id="${category.id}"
          data-field="limit"
        />
        <input
          type="text"
          value="${escapeAttribute(category.note || "")}"
          placeholder="Комментарий"
          data-bank-id="${bankId}"
          data-category-id="${category.id}"
          data-field="note"
        />
        <button
          class="danger-button"
          data-delete-category
          data-bank-id="${bankId}"
          data-category-id="${category.id}"
          type="button"
        >
          Удалить
        </button>
      </div>
    </div>
  `;
}

function renderSummary() {
  const rows = buildSummaryRows();

  if (!rows.length) {
    summaryTableWrap.innerHTML = `
      <div class="empty-state">
        <h3>Нет данных для сводки</h3>
        <p>Когда добавите категории по банкам, здесь появится сравнение лучших ставок.</p>
      </div>
    `;
    return;
  }

  summaryTableWrap.innerHTML = `
    <table class="summary-table">
      <thead>
        <tr>
          <th>Категория</th>
          <th>Лучший банк</th>
          <th>Ставка</th>
          <th>Все предложения</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.name)}</td>
                <td>${escapeHtml(row.bestBank)}</td>
                <td><span class="summary-rate">${formatRate(row.bestRate)}</span></td>
                <td>${escapeHtml(row.offers)}</td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderCategoryDirectory() {
  const groups = buildCategoryDirectoryGroups();
  const query = categorySearchInput.value.trim();
  const filteredGroups = filterCategoryGroups(groups, query);

  if (!groups.length) {
    categorySearchStatus.textContent = "Пока нет данных за выбранный месяц.";
    categoryDirectory.innerHTML = `
      <div class="empty-state">
        <h3>Нет данных по категориям</h3>
        <p>Когда добавите кешбек за месяц, здесь появится список категорий по банкам.</p>
      </div>
    `;
    return;
  }

  if (!filteredGroups.length) {
    categorySearchStatus.textContent = `По запросу "${query}" ничего не найдено.`;
    categoryDirectory.innerHTML = `
      <div class="empty-state">
        <h3>Ничего не найдено</h3>
        <p>Попробуйте другое слово: например, аптеки, транспорт, одежда или название банка.</p>
      </div>
    `;
    return;
  }

  const offerCount = filteredGroups.reduce((sum, group) => sum + group.offers.length, 0);
  categorySearchStatus.textContent = query
    ? `Найдено категорий: ${filteredGroups.length}, предложений: ${offerCount}.`
    : `Категорий: ${filteredGroups.length}, предложений: ${offerCount}.`;

  categoryDirectory.innerHTML = filteredGroups
    .map(
      (group) => `
        <article class="category-card">
          <h3>${escapeHtml(group.category)}</h3>
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
                      <div class="summary-rate">${formatRate(offer.rate)}</div>
                    </div>
                    ${
                      offer.meta
                        ? `<div class="category-offer-note">${escapeHtml(offer.meta)}</div>`
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

function renderMonthStatus() {
  const monthData = ensureMonth(state.selectedMonth);
  const banksWithData = state.data.banks.filter((bank) => {
    const bankData = ensureBankMonthData(monthData, bank.id);
    return bankData.categories.some((category) => normalizeText(category.name));
  }).length;
  const totalCategories = Object.values(monthData.banks).reduce(
    (sum, bankData) =>
      sum + bankData.categories.filter((category) => normalizeText(category.name)).length,
    0,
  );

  monthStatus.textContent = `${formatMonth(state.selectedMonth)}: заполнено банков ${banksWithData} из ${state.data.banks.length}, категорий ${totalCategories}.`;
}

function buildSummaryRows() {
  const monthData = ensureMonth(state.selectedMonth);
  const groups = new Map();

  for (const bank of state.data.banks) {
    const bankData = ensureBankMonthData(monthData, bank.id);
    for (const category of bankData.categories) {
      const name = category.name.trim();
      if (!name) {
        continue;
      }

      const key = normalizeText(name);
      if (!groups.has(key)) {
        groups.set(key, {
          name,
          offers: [],
        });
      }

      groups.get(key).offers.push({
        bankName: bank.name,
        rate: Number(category.rate || 0),
        limit: category.limit?.trim() || "",
        note: category.note?.trim() || "",
      });
    }
  }

  return Array.from(groups.values())
    .map((group) => {
      const sortedOffers = [...group.offers].sort((left, right) => right.rate - left.rate);
      const best = sortedOffers[0];
      return {
        name: group.name,
        bestBank: best.bankName,
        bestRate: best.rate,
        offers: sortedOffers
          .map((offer) => {
            const extras = [offer.limit, offer.note].filter(Boolean).join(", ");
            return extras
              ? `${offer.bankName} ${formatRate(offer.rate)} (${extras})`
              : `${offer.bankName} ${formatRate(offer.rate)}`;
          })
          .join(" • "),
      };
    })
    .sort((left, right) => right.bestRate - left.bestRate || left.name.localeCompare(right.name, "ru"));
}

function buildCategoryDirectoryGroups() {
  const monthData = ensureMonth(state.selectedMonth);
  const groups = new Map();

  for (const bank of state.data.banks) {
    const bankData = ensureBankMonthData(monthData, bank.id);
    for (const category of bankData.categories) {
      const rawName = category.name.trim();
      if (!rawName) {
        continue;
      }

      const { topCategory, offerName } = splitCategoryName(rawName);
      if (!groups.has(topCategory)) {
        groups.set(topCategory, []);
      }

      const metaParts = [category.limit?.trim(), category.note?.trim()].filter(Boolean);
      groups.get(topCategory).push({
        bankName: bank.name,
        label: offerName,
        rate: Number(category.rate || 0),
        meta: metaParts.join(" | "),
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
              [offer.bankName, offer.label, offer.meta, offer.rawName].filter(Boolean).join(" "),
              query,
            ),
          );

      return {
        ...group,
        offers,
      };
    })
    .filter((group) => group.offers.length > 0);
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

function findOrCreateBank(name) {
  const normalizedName = normalizeText(name);
  let bank = state.data.banks.find((item) => normalizeText(item.name) === normalizedName);
  if (!bank) {
    bank = {
      id: createId("bank"),
      name: name.trim(),
    };
    state.data.banks.push(bank);
  }
  return bank;
}

function scheduleSave() {
  window.clearTimeout(state.saveTimeout);
  setSaveStatus("Сохраняю...", "pending");
  state.saveTimeout = window.setTimeout(async () => {
    try {
      await saveData(state.data);
      setSaveStatus("Сохранено", "idle");
      renderBankList();
    } catch (error) {
      console.error(error);
      setSaveStatus("Ошибка сохранения", "error");
    }
  }, 500);
}

async function persistAndRender(message) {
  try {
    setSaveStatus("Сохраняю...", "pending");
    await saveData(state.data);
    setSaveStatus(message, "idle");
    render();
  } catch (error) {
    console.error(error);
    setSaveStatus("Ошибка сохранения", "error");
  }
}

async function fetchData() {
  const response = await fetch(DATA_URL);
  if (!response.ok) {
    throw new Error("Не удалось получить данные");
  }
  return response.json();
}

async function saveData(data) {
  const response = await fetch(DATA_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error("Не удалось сохранить данные");
  }
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

function setSaveStatus(message, tone) {
  saveStatus.textContent = message;
  saveStatus.className = `save-status save-status-${tone}`;
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

function getPreviousMonth(monthKey) {
  const [year, month] = monthKey.split("-").map(Number);
  const date = new Date(year, month - 2, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
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

function normalizeText(value) {
  return String(value || "").trim().toLocaleLowerCase("ru-RU");
}

function splitCategoryName(value) {
  const parts = value.split("/").map((part) => part.trim()).filter(Boolean);
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

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}
