/* Report owns prose and containers; the same iframe instance owns the figure in both views. */
(() => {
  const containers = [...document.querySelectorAll('[data-sf-figure]')];
  for (const container of containers) {
    container.querySelector('[data-sf-expand]').addEventListener('click', () => {
      const expanded = container.classList.toggle('sf-expanded');
      container.querySelector('[data-sf-expand]').setAttribute('aria-expanded', String(expanded));
    });
  }
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') containers.forEach(container => {
      container.classList.remove('sf-expanded');
      container.querySelector('[data-sf-expand]').setAttribute('aria-expanded', 'false');
    });
  });
  async function serializeHtml() {
    const clone = document.documentElement.cloneNode(true);
    for (const container of containers) {
      const api = container.querySelector('iframe').contentWindow.ScientificFigure;
      if (!api) throw new Error(`Figure ${container.dataset.sfFigure} is not ready; report was not saved.`);
      await api.ready;
      const target = [...clone.querySelectorAll('[data-sf-figure]')].find(el => el.dataset.sfFigure === container.dataset.sfFigure);
      target.querySelector('iframe').setAttribute('srcdoc', api.serializeHtml());
      target.classList.remove('sf-expanded');
      target.querySelector('[data-sf-expand]').setAttribute('aria-expanded', 'false');
    }
    clone.querySelectorAll('[contenteditable]').forEach(el => el.setAttribute('contenteditable', 'false'));
    return '<!doctype html>\n' + clone.outerHTML;
  }
  window.ScientificReport = Object.freeze({version: 1, serializeHtml});
  document.querySelector('[data-sf-save-report]')?.addEventListener('click', async () => {
    try {
      const content = await serializeHtml();
      const url = URL.createObjectURL(new Blob([content], {type: 'text/html'}));
      const link = document.createElement('a'); link.href = url; link.download = 'report-edited.html'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) { alert(error.message); }
  });
})();
