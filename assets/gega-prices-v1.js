(() => {
  'use strict';
  const root = document.querySelector('.gega-prices');
  if (!root) return;
  const select = root.querySelector('#gega-period');
  const panels = [...root.querySelectorAll('[data-gega-period]')];
  if (!select || !panels.length) return;
  const show = () => {
    if (!panels.some(panel => panel.dataset.gegaPeriod === select.value)) return;
    for (const panel of panels) panel.hidden = panel.dataset.gegaPeriod !== select.value;
  };
  select.disabled = false;
  select.addEventListener('change', show);
  show();
})();
