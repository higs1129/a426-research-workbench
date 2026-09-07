/* Development-only browser regression. Real layout boxes, no mocked font metrics. */
(async () => {
  const result = document.createElement('pre'); result.id = 'regression-result'; document.body.append(result);
  const assertions = [];
  const assert = (value, label) => { if (!value) throw Error(label); assertions.push(label); };
  const near = (a, b, label, tolerance = 0.02) => assert(Math.abs(a - b) <= tolerance, `${label}: ${a} vs ${b}`);
  const settle = win => new Promise(resolve => win.requestAnimationFrame(() => win.requestAnimationFrame(resolve)));
  const wait = async predicate => { for (let i = 0; i < 200; i++) { if (predicate()) return; await new Promise(r => setTimeout(r, 20)); } throw Error('component readiness timeout'); };
  function geometry(win) {
    const svg = win.document.querySelector('.sf-figure-host svg'), root = svg.getBoundingClientRect();
    const box = selector => {
      const b = svg.querySelector(selector).getBoundingClientRect();
      return [(b.x-root.x)/root.width, (b.y-root.y)/root.height, b.width/root.width, b.height/root.height];
    };
    return {ticks: [...svg.querySelectorAll('#sf-x-tick-labels text')].map(el => el.textContent),
      legend: [...svg.querySelectorAll('#sf-legend text')].map(el => el.textContent),
      bounds: ['#sf-dynamic-geometry', '#sf-x-tick-labels', '#sf-y-tick-labels', '#sf-legend', '#sf-x-axis-label', '#sf-y-axis-label'].map(box),
      font: win.getComputedStyle(svg.querySelector('#sf-x-axis-label text')).fontSize};
  }
  function gaps(win) {
    const svg = win.document.querySelector('.sf-figure-host svg'), scale = svg.getScreenCTM().a;
    const x = svg.querySelector('#sf-x-axis-label text'), y = svg.querySelector('#sf-y-axis-label text');
    const xb = x.getBoundingClientRect(), yb = y.getBoundingClientRect();
    const ticksX = [...svg.querySelectorAll('#sf-x-tick-labels text')].map(el => el.getBoundingClientRect());
    const ticksY = [...svg.querySelectorAll('#sf-y-tick-labels text')].map(el => el.getBoundingClientRect());
    near((xb.top - Math.max(...ticksX.map(b=>b.bottom)))/(parseFloat(win.getComputedStyle(x).fontSize)*scale), 0.3, 'x title rendered gap/em');
    near((Math.min(...ticksY.map(b=>b.left))-yb.right)/(parseFloat(win.getComputedStyle(y).fontSize)*scale), 0.2, 'y title rendered gap/em');
  }
  try {
    const containers = [...document.querySelectorAll('[data-sf-figure]')];
    for (const container of containers) {
      container.scrollIntoView();
      const frame = container.querySelector('iframe');
      await wait(() => frame.contentWindow.ScientificFigure);
      const win = frame.contentWindow, api = win.ScientificFigure;
      await api.ready; await settle(win);
      assert(geometry(win).ticks.join(',') === '1,4,7,10,13,16', 'confirmed fixed ticks');
      const before = geometry(win), state = JSON.stringify(api.getState()); gaps(win);
      assert(before.legend.length === (container.dataset.sfFigure === 'scatter' ? 1 : 2), 'legend retained');
      container.querySelector('[data-sf-expand]').click(); await settle(win);
      assert(frame.contentWindow === win && win.ScientificFigure === api, 'expanded view keeps the same instance');
      const expanded = geometry(win);
      assert(JSON.stringify(api.getState()) === state, 'opening viewer preserves complete state');
      assert(JSON.stringify(before.ticks) === JSON.stringify(expanded.ticks), 'ticks match between sizes');
      assert(JSON.stringify(before.legend) === JSON.stringify(expanded.legend), 'legend matches between sizes');
      before.bounds.flat().forEach((value, i) => near(value, expanded.bounds.flat()[i], 'normalized geometry', 0.003));
      assert(before.font === expanded.font, 'font tokens unchanged'); gaps(win);
      container.querySelector('[data-sf-expand]').click(); await settle(win);
      const input = win.document.querySelector('[data-sf-field="xLabel"]');
      input.value = 'Edited sample label'; input.dispatchEvent(new win.Event('input', {bubbles:true}));
      api.setView({xMin: 2, xMax: 12, yMin: 10, yMax: 50}); await settle(win); gaps(win);
      const exported = api.exportCurrentSvg();
      const exportPreview = win.document.createElement('div');
      exportPreview.style.width = win.document.querySelector('.sf-figure-host svg').getBoundingClientRect().width + 'px';
      exportPreview.innerHTML = exported;
      exportPreview.querySelector('svg').style.width='100%'; exportPreview.querySelector('svg').style.height='auto';
      win.document.body.append(exportPreview); await settle(win);
      const liveSvg = win.document.querySelector('.sf-figure-host svg'), exportSvg = exportPreview.querySelector('svg');
      for (const role of ['sf-x-axis-label','sf-y-axis-label','sf-x-tick-labels','sf-y-tick-labels','sf-legend','sf-dynamic-geometry']) {
        const normalized = (svg, el) => { const outer=svg.getBoundingClientRect(), b=el.getBoundingClientRect(); return [(b.x-outer.x)/outer.width,(b.y-outer.y)/outer.height,b.width/outer.width,b.height/outer.height]; };
        const a=normalized(liveSvg,liveSvg.querySelector('#'+role));
        const b=normalized(exportSvg,exportSvg.querySelector(`[id$="-${role}"]`));
        a.forEach((value,i)=>near(value,b[i],'current export rendered geometry',0.003));
      }
      exportPreview.remove();
      const xml = new DOMParser().parseFromString(exported, 'image/svg+xml');
      assert(!xml.querySelector('parsererror'), 'SVG parses');
      assert(xml.documentElement.dataset.exportState === 'current', 'export explicitly current state');
      const model = JSON.parse(xml.querySelector('[data-role="figure-model"]').textContent);
      assert(model.x.domain.join(',') === '2,12', 'export has current domain');
      assert(model.x.title === 'Edited sample label', 'export has edited text');
      assert(!xml.querySelector('[data-sf-editor-only], [data-sf-interaction-surface], .sf-transient'), 'export omits transient UI');
      const ids = new Set([...xml.querySelectorAll('[id]')].map(el => el.id));
      for (const element of xml.querySelectorAll('*')) for (const attr of element.attributes) {
        for (const match of attr.value.matchAll(/url\(#([^\)]+)\)/g)) assert(ids.has(match[1]), 'export local references resolve');
      }
      const archive = document.createElement('textarea'); archive.dataset.exportedSvg = container.dataset.sfFigure; archive.textContent = exported; document.body.append(archive);
    }
    document.querySelector('#report-prose').textContent = 'Edited report text';
    const saved = await ScientificReport.serializeHtml();
    const reopened = document.createElement('iframe'); reopened.style.width='800px'; reopened.style.height='700px';
    // Reopen in a fresh document without replaying this test harness.
    const savedDoc = new DOMParser().parseFromString(saved, 'text/html');
    savedDoc.querySelector('#regression-harness').remove(); savedDoc.querySelector('#regression-result').remove();
    reopened.srcdoc = savedDoc.documentElement.outerHTML; document.body.append(reopened);
    await wait(() => reopened.contentDocument.querySelector('[data-sf-figure] iframe')?.contentWindow.ScientificFigure);
    assert(reopened.contentDocument.querySelector('#report-prose').textContent === 'Edited report text', 'report prose survives save/reopen');
    for (const frame of reopened.contentDocument.querySelectorAll('[data-sf-figure] iframe')) {
      await wait(() => frame.contentWindow.ScientificFigure); await frame.contentWindow.ScientificFigure.ready;
      const state = frame.contentWindow.ScientificFigure.getState();
      assert(state.view.xMin === 2 && state.view.xMax === 12, 'view survives save/reopen');
      assert(state.style.xLabel === 'Edited sample label', 'figure text survives save/reopen');
      gaps(frame.contentWindow);
    }
    result.textContent = JSON.stringify({ok: true, count: assertions.length});
  } catch (error) { result.textContent = JSON.stringify({ok:false, error:error.stack, assertions}); }
  result.dataset.finished = 'true';
})();
