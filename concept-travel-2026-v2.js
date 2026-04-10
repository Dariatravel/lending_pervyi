(() => {
  const tabs = Array.from(document.querySelectorAll("[data-modern-tab]"));
  const title = document.querySelector("[data-modern-title]");
  const text = document.querySelector("[data-modern-text]");
  const cta = document.querySelector("[data-modern-cta]");

  const content = {
    first: {
      title: "Едем впервые и хотим без ошибок выбрать район",
      text: "Сайт должен быстро объяснить разницу между Сухумом, Лдзаа, Пицундой, Гагрой и Новым Афоном, а потом показать подходящие объекты без перегруза.",
      cta: "Получить спокойную подборку",
    },
    family: {
      title: "С детьми нужен понятный и удобный отдых",
      text: "Приоритеты здесь другие: короткая дорога до моря, удобный пляж, питание, тишина ночью и минимум бытового стресса на месте.",
      cta: "Подобрать семейные варианты",
    },
    couple: {
      title: "Для пары нужен красивый, но не нервный сценарий",
      text: "Важно показать атмосферу, виды, ужины, прогулки и честно обозначить, где будет уютно, а где слишком шумно и туристически тяжело.",
      cta: "Подобрать для пары",
    },
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((item) => item.classList.remove("is-active"));
      tab.classList.add("is-active");
      const next = content[tab.dataset.modernTab];
      if (!next) return;
      if (title) title.textContent = next.title;
      if (text) text.textContent = next.text;
      if (cta) cta.textContent = next.cta;
    });
  });

  const toggles = Array.from(document.querySelectorAll("[data-modern-toggle]"));
  toggles.forEach((button) => {
    button.addEventListener("click", () => {
      const wrap = button.closest(".landing2026__accordion");
      const panel = wrap?.querySelector(".landing2026__accordion-panel");
      const icon = button.querySelector("[data-modern-icon]");
      if (!panel || !icon) return;
      const isHidden = panel.hasAttribute("hidden");
      panel.toggleAttribute("hidden", !isHidden);
      icon.textContent = isHidden ? "−" : "+";
    });
  });
})();
