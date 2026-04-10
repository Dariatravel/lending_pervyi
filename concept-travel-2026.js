(() => {
  const tabs = Array.from(document.querySelectorAll("[data-scenario-tab]"));
  const title = document.querySelector("[data-search-title]");
  const summary = document.querySelector("[data-search-summary]");
  const submit = document.querySelector("[data-search-submit]");

  const scenarioMap = {
    first: {
      title: "Первый отпуск в Абхазии",
      summary: "Подберём понятный район, проверенный пляж и жильё без неприятных сюрпризов по дороге, заселению и быту.",
      button: "Получить спокойную подборку",
    },
    family: {
      title: "С детьми и без лишней логистики",
      summary: "Сразу отсечём шумные локации, крутые подъёмы, неудобные пляжи и варианты без нормальной инфраструктуры рядом.",
      button: "Подобрать для семьи",
    },
    couple: {
      title: "Для пары: красиво, тихо, без хаоса",
      summary: "Покажем уютные отели и домики с атмосферой, видами, завтраками и маршрутом, который не испортит отдых.",
      button: "Подобрать для пары",
    },
    help: {
      title: "Нужна помощь с выбором района",
      summary: "Если вы впервые едете в Абхазию, мы сначала объясним разницу между Сухумом, Лдзаа, Пицундой, Гагрой и Новым Афоном.",
      button: "Получить консультацию",
    },
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((item) => item.classList.remove("is-active"));
      tab.classList.add("is-active");
      const next = scenarioMap[tab.dataset.scenarioTab];
      if (!next) return;
      if (title) title.textContent = next.title;
      if (summary) summary.textContent = next.summary;
      if (submit) submit.textContent = next.button;
    });
  });

  const toggles = Array.from(document.querySelectorAll("[data-toggle]"));
  toggles.forEach((button) => {
    button.addEventListener("click", () => {
      const wrap = button.closest(".concept-toggle");
      const panel = wrap?.querySelector(".concept-toggle__panel");
      const icon = button.querySelector("[data-toggle-icon]");
      if (!panel || !icon) return;
      const isHidden = panel.hasAttribute("hidden");
      panel.toggleAttribute("hidden", !isHidden);
      icon.textContent = isHidden ? "−" : "+";
    });
  });
})();
