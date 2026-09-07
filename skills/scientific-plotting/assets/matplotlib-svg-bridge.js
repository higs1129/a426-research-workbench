/* Fixed bridge for standard single-axes Matplotlib SVG figures.
 * Matplotlib owns the initial vector figure. This bridge reuses authoritative
 * series data for browser inspection and viewport changes; task code does not
 * author SVG coordinates or interaction handlers.
 */
(function attachMatplotlibSvgBridge() {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const originalDocument = "<!doctype html>\n" + document.documentElement.outerHTML;
  const root = document.getElementById("figure-root");
  const svg = root.querySelector("svg");
  const surface = document.getElementById("interaction-surface");
  const brush = document.getElementById("zoom-brush");
  const geometry = document.getElementById("sf-dynamic-geometry");
  const tickLayer = document.getElementById("sf-dynamic-ticks");
  const inspection = document.getElementById("inspection-overlay");
  const status = document.getElementById("sf-status");
  const profile = JSON.parse(document.getElementById("scientific-figure-profile").textContent);
  const data = JSON.parse(document.getElementById("scientific-figure-data").textContent);
  const bounds = data.plotBounds;
  const fullView = data.fullView;
  const layoutRoles = Object.freeze({
    title: {id: "sf-figure-title", label: "Figure title"},
    xLabel: {id: "sf-x-axis-label", label: "X-axis label"},
    yLabel: {id: "sf-y-axis-label", label: "Y-axis label"},
    xTicks: {id: "sf-x-tick-labels", label: "X-axis tick labels"},
    yTicks: {id: "sf-y-tick-labels", label: "Y-axis tick labels"},
    legend: {id: "sf-legend", label: "Legend"},
  });

  function copyLayout(layout = {}) {
    return Object.fromEntries(Object.keys(layoutRoles).map(role => [
      role,
      {x: Number(layout[role]?.x || 0), y: Number(layout[role]?.y || 0)},
    ]));
  }

  const markerSeries = data.series.filter(item => item.type === "scatter" || item.showMarkers);
  const defaultMarkerSizes = Object.freeze(Object.fromEntries(markerSeries.map(item => [
    item.id,
    Number(item.markerPt ?? profile.markerPt),
  ])));
  const firstMarkerSize = markerSeries.length ? defaultMarkerSizes[markerSeries[0].id] : Number(profile.markerPt);

  const defaults = Object.freeze({
    title: data.labels.title,
    xLabel: data.labels.x,
    yLabel: data.labels.y,
    fontFamily: 'Calibri, "Microsoft YaHei", sans-serif',
    plotFontPt: Number(profile.tickPt),
    axisFontPt: Number(profile.axisLabelPt),
    titleFontPt: Number(profile.figureTitlePt),
    lineWidthPt: Number(data.series[0]?.lineWidthPt || profile.rawWidthPt),
    markerSizePt: firstMarkerSize,
    markerSizes: defaultMarkerSizes,
    layout: copyLayout(data.layoutDefaults),
  });
  let styleState = {...defaults, markerSizes: {...defaults.markerSizes}, layout: copyLayout(defaults.layout)};
  const stateStore = ScientificFigureRuntime.createStateStore(`sf-mpl:${data.figureId}`, 3);
  // Portable embedded state is authoritative. Browser caches never change an initial report view.
  const embeddedState = JSON.parse(document.getElementById("scientific-figure-state")?.textContent || "null");
  const saved = embeddedState?.figureId === data.figureId ? embeddedState.style : null;
  let automaticTopLayout = !(saved && typeof saved === "object");
  if (saved && typeof saved === "object") {
    styleState = {
      ...styleState,
      ...saved,
      markerSizes: {...defaults.markerSizes, ...(saved.markerSizes || {})},
      layout: copyLayout(saved.layout || defaults.layout),
    };
  }
  const layoutHistory = ScientificFigureRuntime.createHistory(30);
  const baseTransforms = new Map();
  let layoutMode = false;
  let selectedRole = null;
  let layoutDrag = null;
  let layoutInputStart = null;
  let topLayoutFrame = 0;

  function node(name, attributes = {}, text = null) {
    const element = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attributes)) {
      element.setAttribute(key, String(value));
    }
    if (text != null) element.textContent = text;
    return element;
  }

  function mapX(value, view) {
    return bounds.left + (value - view.xMin) / (view.xMax - view.xMin) * (bounds.right - bounds.left);
  }

  function mapY(value, view) {
    return bounds.bottom - (value - view.yMin) / (view.yMax - view.yMin) * (bounds.bottom - bounds.top);
  }

  function niceTicks(minimum, maximum, targetCount = 6) {
    const span = maximum - minimum;
    if (!(span > 0)) return [minimum];
    const rough = span / Math.max(2, targetCount - 1);
    const power = 10 ** Math.floor(Math.log10(rough));
    const fraction = rough / power;
    const niceFraction = [1, 2, 2.5, 5, 10].find(value => value >= fraction) || 10;
    const step = niceFraction * power;
    const first = Math.ceil((minimum - step * 1e-9) / step) * step;
    const values = [];
    for (let value = first; value <= maximum + step * 1e-9; value += step) {
      values.push(Number(value.toPrecision(12)));
      if (values.length > 20) break;
    }
    return values;
  }

  function fixedStepTicks(minimum, maximum, specification) {
    const step = Math.abs(Number(specification.step));
    const reference = Number(specification.reference || 0);
    if (!(step > 0) || !Number.isFinite(reference)) return [];
    const tolerance = step * 1e-9;
    const firstIndex = Math.ceil((minimum - reference - tolerance) / step);
    const lastIndex = Math.floor((maximum - reference + tolerance) / step);
    const values = [];
    for (let index = firstIndex; index <= lastIndex; index += 1) {
      values.push(Number((reference + index * step).toPrecision(12)));
      if (values.length > 500) break;
    }
    return values;
  }

  function ticksForAxis(axis, minimum, maximum) {
    if (minimum === fullView[`${axis}Min`] && maximum === fullView[`${axis}Max`] && data.initialTicks?.[axis]) {
      return data.initialTicks[axis].map(tick => tick.value);
    }
    const specification = data.ticks?.[axis] || {mode: "nice"};
    if (specification.mode === "fixed-step") {
      return fixedStepTicks(minimum, maximum, specification);
    }
    if (specification.mode === "fixed-values") {
      return (specification.values || []).filter(value => value >= minimum && value <= maximum);
    }
    return niceTicks(
      minimum,
      maximum,
      Number(specification.targetCount || profile.majorTickTarget),
    );
  }

  function formatValue(value) {
    const absolute = Math.abs(value);
    if (absolute !== 0 && (absolute >= 1e4 || absolute < 1e-3)) return value.toExponential(2);
    return Number(value.toFixed(6)).toString();
  }

  function hideMatplotlibDynamicNodes() {
    for (const item of data.series) {
      const source = document.getElementById(item.sourceId);
      if (source) source.style.display = "none";
    }
    svg.querySelectorAll("g[id^='xtick_'], g[id^='ytick_']").forEach(element => {
      element.style.display = "none";
    });
  }

  function renderMarkers(item, view) {
    const radius = Math.max(0.25, Number(styleState.markerSizes[item.id] ?? styleState.markerSizePt) / 2);
    item.x.forEach((xValue, index) => {
      const yValue = item.y[index];
      if (xValue == null || yValue == null) return;
      if (xValue < view.xMin || xValue > view.xMax || yValue < view.yMin || yValue > view.yMax) return;
      geometry.appendChild(node("circle", {
        cx: mapX(xValue, view), cy: mapY(yValue, view), r: radius,
        fill: item.color, opacity: item.opacity, "data-sf-series-id": item.id,
      }));
    });
  }

  function renderGeometry(view) {
    geometry.replaceChildren();
    for (const item of data.series) {
      if (item.type === "scatter") {
        renderMarkers(item, view);
        continue;
      }
      let path = "";
      let drawing = false;
      item.x.forEach((xValue, index) => {
        const yValue = item.y[index];
        if (xValue == null || yValue == null) {
          drawing = false;
          return;
        }
        const x = mapX(xValue, view);
        const y = mapY(yValue, view);
        path += `${drawing ? "L" : "M"}${x.toFixed(3)},${y.toFixed(3)}`;
        drawing = true;
      });
      geometry.appendChild(node("path", {
        d: path,
        fill: "none",
        stroke: item.color,
        "data-role": "data-series", "data-series-id": item.id,
        "stroke-width": item.lineWidthPt * styleState.lineWidthPt / (defaults.lineWidthPt || 1),
        "stroke-dasharray": item.dash || "none",
        opacity: item.opacity,
      }));
      if (item.showMarkers) renderMarkers(item, view);
    }
  }

  function renderTicks(view) {
    tickLayer.replaceChildren();
    const xMarks = node("g", {"data-sf-tick-marks": "x", "data-role": "ticks-x"});
    const xLabels = node("g", {id: "sf-x-tick-labels"});
    const yMarks = node("g", {"data-sf-tick-marks": "y", "data-role": "ticks-y"});
    const yLabels = node("g", {id: "sf-y-tick-labels"});
    tickLayer.append(xMarks, xLabels, yMarks, yLabels);
    tickLayer.setAttribute("font-family", styleState.fontFamily);
    tickLayer.setAttribute("font-size", styleState.plotFontPt);
    tickLayer.setAttribute("font-weight", "700");
    tickLayer.setAttribute("fill", "black");
    tickLayer.setAttribute("pointer-events", "none");
    const tickLength = Math.max(2.5, Number(profile.axisWidthPt) * 4.5);
    const tickGap = Number(profile.tickLabelGapEm) * styleState.plotFontPt;
    for (const value of ticksForAxis("x", view.xMin, view.xMax)) {
      const x = mapX(value, view);
      xMarks.appendChild(node("line", {
        x1: x, x2: x, y1: bounds.bottom, y2: bounds.bottom + tickLength,
        stroke: "black", "stroke-width": profile.axisWidthPt, "data-sf-axis": "x",
      }));
      xLabels.appendChild(node("text", {
        x, y: bounds.bottom + tickLength + tickGap,
        "text-anchor": "middle", "dominant-baseline": "hanging",
        "data-sf-axis": "x", "data-sf-tick-label": "true",
      }, initialTickLabel("x", value, view)));
    }
    for (const value of ticksForAxis("y", view.yMin, view.yMax)) {
      const y = mapY(value, view);
      yMarks.appendChild(node("line", {
        x1: bounds.left - tickLength, x2: bounds.left, y1: y, y2: y,
        stroke: "black", "stroke-width": profile.axisWidthPt, "data-sf-axis": "y",
      }));
      yLabels.appendChild(node("text", {
        x: bounds.left - tickLength - tickGap, y,
        "text-anchor": "end", "dominant-baseline": "middle",
        "data-sf-axis": "y", "data-sf-tick-label": "true",
      }, initialTickLabel("y", value, view)));
    }
    markLayoutElement("xTicks");
    markLayoutElement("yTicks");
    applyLayoutRole("xTicks");
    applyLayoutRole("yTicks");
    const xTitle = document.querySelector("#sf-x-axis-label text");
    requestAnimationFrame(() => {
      const xTickLabels = Array.from(xLabels.querySelectorAll("text[data-sf-axis='x']"));
      const targetTop = bounds.bottom + tickLength + tickGap;
      for (const label of xTickLabels) {
        const box = label.getBBox();
        const currentY = Number(label.getAttribute("y"));
        label.setAttribute("y", (currentY + targetTop - box.y).toFixed(3));
      }
      placeAxisTitles();
      refreshLayoutHitTarget(layoutElement("xLabel"));
      refreshLayoutHitTarget(xLabels);
      refreshLayoutHitTarget(yLabels);
    });
  }

  function renderView(view) {
    renderGeometry(view);
    renderTicks(view);
  }

  function initialTickLabel(axis, value, view) {
    if (view[`${axis}Min`] === fullView[`${axis}Min`] && view[`${axis}Max`] === fullView[`${axis}Max`]) {
      const tick = data.initialTicks?.[axis]?.find(item => item.value === value);
      if (tick) return tick.label;
    }
    return formatValue(value);
  }

  function placeAxisTitles() {
    const scale = Math.abs(svg.getScreenCTM()?.a || 1);
    for (const axis of ["x", "y"]) {
      const role = `${axis}Label`, group = layoutElement(role);
      const labels = [...document.querySelectorAll(`#sf-${axis}-tick-labels text`)];
      if (!group || !labels.length) continue;
      applyLayoutRole(role);
      const title = group.querySelector("text").getBoundingClientRect();
      const boxes = labels.map(label => label.getBoundingClientRect());
      const gap = profile[axis === "x" ? "axisTitleGapEmX" : "axisTitleGapEmY"] * styleState.axisFontPt;
      const offset = styleState.layout[role] || {x: 0, y: 0};
      const delta = axis === "x"
        ? (Math.max(...boxes.map(box => box.bottom)) - title.top) / scale + gap + offset.y
        : (Math.min(...boxes.map(box => box.left)) - title.right) / scale - gap + offset.x;
      group.setAttribute("transform", `translate(${axis === "y" ? delta : 0} ${axis === "x" ? delta : 0}) ${group.getAttribute("transform") || ""}`);
      group.setAttribute("data-gap-method", "rendered-bounds");
    }
  }

  function nearestPoint(plot, view) {
    let best = null;
    let bestDistance = Infinity;
    for (const item of data.series) {
      item.x.forEach((xValue, index) => {
        const yValue = item.y[index];
        if (xValue == null || yValue == null) return;
        if (xValue < view.xMin || xValue > view.xMax || yValue < view.yMin || yValue > view.yMax) return;
        const x = mapX(xValue, view);
        const y = mapY(yValue, view);
        const distance = (x - plot.x) ** 2 + (y - plot.y) ** 2;
        if (distance < bestDistance) {
          bestDistance = distance;
          best = {series: item.label, xValue, yValue, x, y, color: item.color};
        }
      });
    }
    return bestDistance <= 24 ** 2 ? best : null;
  }

  function clearInspection() {
    inspection.replaceChildren();
    inspection.setAttribute("visibility", "hidden");
  }

  function renderInspection(result) {
    clearInspection();
    inspection.setAttribute("visibility", "visible");
    inspection.appendChild(node("line", {
      x1: bounds.left, x2: bounds.right, y1: result.y, y2: result.y,
      stroke: result.color, "stroke-width": 0.8, "stroke-dasharray": "4 3",
    }));
    inspection.appendChild(node("line", {
      x1: result.x, x2: result.x, y1: bounds.top, y2: bounds.bottom,
      stroke: result.color, "stroke-width": 0.8, "stroke-dasharray": "4 3",
    }));
    inspection.appendChild(node("circle", {
      cx: result.x, cy: result.y, r: Math.max(2.5, profile.markerPt / 2),
      fill: result.color, stroke: "white", "stroke-width": 0.8,
    }));

    const titleText = result.series;
    const valueText = `${formatValue(result.xValue)}, ${formatValue(result.yValue)}`;
    const boxWidth = Math.min(150, Math.max(58, Math.max(titleText.length * profile.hoverTitlePt * 0.58, valueText.length * profile.hoverValuePt * 0.58) + 12));
    const boxHeight = profile.hoverTitlePt + profile.hoverValuePt + 15;
    const useLeft = result.x + boxWidth + 10 > bounds.right;
    const boxX = useLeft ? result.x - boxWidth - 8 : result.x + 8;
    const boxY = Math.max(bounds.top + 3, Math.min(bounds.bottom - boxHeight - 3, result.y - boxHeight / 2));
    inspection.appendChild(node("rect", {
      x: boxX, y: boxY, width: boxWidth, height: boxHeight, rx: 3,
      fill: "white", stroke: result.color, "stroke-width": 0.8, opacity: 0.96,
    }));
    inspection.appendChild(node("text", {
      x: boxX + 6, y: boxY + 6, "dominant-baseline": "hanging",
      fill: "black", "font-family": styleState.fontFamily,
      "font-size": profile.hoverTitlePt, "font-weight": "700",
    }, titleText));
    inspection.appendChild(node("text", {
      x: boxX + 6, y: boxY + 9 + profile.hoverTitlePt, "dominant-baseline": "hanging",
      fill: "black", "font-family": styleState.fontFamily,
      "font-size": profile.hoverValuePt,
    }, valueText));
  }

  function setText(groupId, value) {
    const text = document.querySelector(`#${groupId} text`);
    if (text) text.textContent = value;
  }

  function layoutElement(role) {
    const descriptor = layoutRoles[role];
    return descriptor ? document.getElementById(descriptor.id) : null;
  }

  function refreshLayoutHitTarget(element) {
    if (!element) return;
    Array.from(element.children).find(child => child.hasAttribute("data-sf-layout-hit"))?.remove();
    let box;
    try {
      box = element.getBBox();
    } catch {
      return;
    }
    if (![box.x, box.y, box.width, box.height].every(Number.isFinite) || box.width <= 0 || box.height <= 0) return;
    const hitTarget = node("rect", {
      x: box.x,
      y: box.y,
      width: box.width,
      height: box.height,
      fill: "transparent",
      "data-sf-layout-hit": "true",
      "data-sf-editor-only": "true",
      "aria-hidden": "true",
    });
    element.insertBefore(hitTarget, element.firstChild);
  }

  function markLayoutElement(role) {
    const descriptor = layoutRoles[role];
    const element = descriptor ? document.getElementById(descriptor.id) : null;
    if (!element) return;
    if (!baseTransforms.has(role)) baseTransforms.set(role, element.getAttribute("transform") || "");
    element.setAttribute("data-sf-layout-role", role);
    element.setAttribute("tabindex", "0");
    if (selectedRole === role) element.setAttribute("data-sf-selected", "true");
    refreshLayoutHitTarget(element);
  }

  function markLayoutElements() {
    for (const role of Object.keys(layoutRoles)) markLayoutElement(role);
  }

  function applyLayoutRole(role) {
    const element = layoutElement(role);
    if (!element) return;
    const offset = styleState.layout[role] || {x: 0, y: 0};
    const move = `translate(${Number(offset.x) || 0} ${Number(offset.y) || 0})`;
    const base = baseTransforms.get(role) || "";
    element.setAttribute("transform", [move, base].filter(Boolean).join(" "));
  }

  function applyLayout() {
    for (const role of Object.keys(layoutRoles)) applyLayoutRole(role);
  }

  function scheduleAutomaticTopLayout() {
    if (!automaticTopLayout) return;
    const frame = ++topLayoutFrame;
    requestAnimationFrame(() => {
      if (!automaticTopLayout || frame !== topLayoutFrame) return;
      const title = layoutElement("title");
      const legend = layoutElement("legend");
      if (!title || !legend) return;
      const titleBox = title.getBoundingClientRect();
      const legendBox = legend.getBoundingClientRect();
      const horizontalOverlap = Math.min(titleBox.right, legendBox.right) > Math.max(titleBox.left, legendBox.left);
      if (!horizontalOverlap) {
        root.dataset.sfTitleLegendLayout = "clear";
        return;
      }
      const scaleY = Math.abs(svg.getScreenCTM()?.d || 1);
      const desiredGapPx = Number(profile.titleLegendGapEm) * styleState.titleFontPt * scaleY;
      const currentGapPx = legendBox.top - titleBox.bottom;
      const requiredMovePx = desiredGapPx - currentGapPx;
      if (requiredMovePx <= 0.1) {
        root.dataset.sfTitleLegendLayout = "clear";
        return;
      }
      const svgBox = svg.getBoundingClientRect();
      const availableMovePx = Math.max(0, titleBox.top - svgBox.top);
      if (requiredMovePx > availableMovePx + 0.5) {
        root.dataset.sfLayoutRisk = "title-legend-overflow";
        status.textContent = "The title and top legend need more vertical room; increase figure height or wrap the legend.";
        return;
      }
      styleState.layout.title.y -= requiredMovePx / scaleY;
      applyLayoutRole("title");
      root.dataset.sfTitleLegendLayout = "adjusted";
    });
  }

  function syncLayoutInspector() {
    const selection = document.getElementById("sf-layout-selection");
    if (selection) selection.textContent = selectedRole ? layoutRoles[selectedRole].label : "None";
    root.querySelectorAll("[data-sf-layout-field]").forEach(input => {
      input.disabled = !selectedRole;
      input.value = selectedRole ? styleState.layout[selectedRole][input.dataset.sfLayoutField] : "";
    });
    const undo = root.querySelector("[data-sf-action='undo-layout']");
    if (undo) undo.disabled = layoutHistory.size() === 0;
  }

  function selectLayoutRole(role) {
    selectedRole = layoutRoles[role] && layoutElement(role) ? role : null;
    for (const candidate of Object.keys(layoutRoles)) {
      const element = layoutElement(candidate);
      if (!element) continue;
      if (candidate === selectedRole) element.setAttribute("data-sf-selected", "true");
      else element.removeAttribute("data-sf-selected");
    }
    syncLayoutInspector();
    if (selectedRole) status.textContent = `${layoutRoles[selectedRole].label} selected. Drag it or edit its offsets.`;
  }

  function setLayoutMode(enabled) {
    layoutMode = Boolean(enabled);
    root.classList.toggle("sf-layout-editing", layoutMode);
    root.querySelector("[data-sf-action='edit-layout']")?.setAttribute("aria-pressed", String(layoutMode));
    surface.style.pointerEvents = layoutMode ? "none" : "all";
    controller.setEnabled(!layoutMode);
    if (!layoutMode) selectLayoutRole(null);
    else status.textContent = "Edit layout: select and drag titles, the legend, or either axis's tick-label group. Tick marks and data geometry stay locked.";
  }

  function eventToSvg(event) {
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  }

  function onLayoutPointerDown(event) {
    if (!layoutMode || event.button !== 0) return;
    const target = event.target.closest?.("[data-sf-layout-role]");
    if (!target) {
      status.textContent = "Only titles, the legend, and the x/y tick-label groups can be moved; tick marks and data geometry are locked.";
      return;
    }
    event.preventDefault();
    const role = target.dataset.sfLayoutRole;
    if (role === "title" || role === "legend") automaticTopLayout = false;
    selectLayoutRole(role);
    const point = eventToSvg(event);
    layoutDrag = {
      role,
      start: point,
      original: {...styleState.layout[role]},
      before: copyLayout(styleState.layout),
      moved: false,
      pointerId: event.pointerId,
    };
    svg.setPointerCapture?.(event.pointerId);
  }

  function onLayoutPointerMove(event) {
    if (!layoutDrag) return;
    event.preventDefault();
    const point = eventToSvg(event);
    const next = {
      x: layoutDrag.original.x + point.x - layoutDrag.start.x,
      y: layoutDrag.original.y + point.y - layoutDrag.start.y,
    };
    if (!layoutDrag.moved && (Math.abs(next.x - layoutDrag.original.x) > 0.05 || Math.abs(next.y - layoutDrag.original.y) > 0.05)) {
      layoutHistory.push(layoutDrag.before);
      layoutDrag.moved = true;
    }
    styleState.layout[layoutDrag.role] = next;
    applyLayoutRole(layoutDrag.role);
    syncLayoutInspector();
  }

  function finishLayoutDrag() {
    if (!layoutDrag) return;
    svg.releasePointerCapture?.(layoutDrag.pointerId);
    if (layoutDrag.moved) stateStore.save(styleState);
    layoutDrag = null;
    syncLayoutInspector();
  }

  function onLayoutKeyDown(event) {
    if (!layoutMode || !["Enter", " "].includes(event.key)) return;
    const target = event.target.closest?.("[data-sf-layout-role]");
    if (!target) return;
    event.preventDefault();
    selectLayoutRole(target.dataset.sfLayoutRole);
  }

  function applyStyle({persist = true} = {}) {
    setText("sf-figure-title", styleState.title);
    setText("sf-x-axis-label", styleState.xLabel);
    setText("sf-y-axis-label", styleState.yLabel);
    svg.querySelectorAll("text").forEach(text => {
      text.style.fontFamily = styleState.fontFamily;
      text.style.fill = "black";
    });
    const title = document.querySelector("#sf-figure-title text");
    if (title) title.style.fontSize = `${styleState.titleFontPt}px`;
    for (const selector of ["#sf-x-axis-label text", "#sf-y-axis-label text"]) {
      const label = document.querySelector(selector);
      if (label) label.style.fontSize = `${styleState.axisFontPt}px`;
    }
    markLayoutElements();
    applyLayout();
    scheduleAutomaticTopLayout();
    syncEditor();
    syncLayoutInspector();
    renderView(controller?.getView?.() || fullView);
    if (persist) stateStore.save(styleState);
  }

  function syncEditor() {
    root.querySelectorAll("[data-sf-field]").forEach(input => {
      input.value = styleState[input.dataset.sfField];
    });
  }

  function downloadSvg() {
    const blob = new Blob([exportCurrentSvg()], {type: "image/svg+xml"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${data.figureId}.svg`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
  }

  hideMatplotlibDynamicNodes();
  let controller = ScientificFigureRuntime.createController({
    root,
    surface,
    brush,
    plotBounds: bounds,
    fullView,
    initialView: embeddedState?.view || fullView,
    pointerMode: embeddedState?.pointerMode || "zoom",
    hooks: {
      viewChanged({view}) { renderView(view); },
      inspect({plot, view}) { return nearestPoint(plot, view); },
      renderInspection,
      clearInspection,
      modeChanged({pointerMode, enabled}) {
        if (!enabled) status.textContent = "Inspection is temporarily disabled.";
        else status.textContent = pointerMode === "pan"
          ? "Pan: left-drag moves both axes; wheel zoom remains active."
          : "Box zoom: left-drag a rectangle; hover reads raw points.";
      },
    },
  });

  root.querySelectorAll("[data-sf-field]").forEach(input => {
    input.addEventListener("input", () => {
      const key = input.dataset.sfField;
      styleState[key] = input.type === "number" ? Number(input.value) : input.value;
      if (key === "markerSizePt") {
        styleState.markerSizes = Object.fromEntries(markerSeries.map(item => [item.id, styleState.markerSizePt]));
      }
      applyStyle();
    });
  });
  root.querySelectorAll("[data-sf-layout-field]").forEach(input => {
    input.addEventListener("focus", () => {
      if (selectedRole === "title" || selectedRole === "legend") automaticTopLayout = false;
      layoutInputStart = copyLayout(styleState.layout);
    });
    input.addEventListener("input", () => {
      if (!selectedRole) return;
      styleState.layout[selectedRole][input.dataset.sfLayoutField] = Number(input.value) || 0;
      applyLayoutRole(selectedRole);
      stateStore.save(styleState);
    });
    input.addEventListener("change", () => {
      if (layoutInputStart && JSON.stringify(layoutInputStart) !== JSON.stringify(styleState.layout)) {
        layoutHistory.push(layoutInputStart);
      }
      layoutInputStart = null;
      syncLayoutInspector();
    });
  });
  svg.addEventListener("pointerdown", onLayoutPointerDown);
  svg.addEventListener("pointermove", onLayoutPointerMove);
  svg.addEventListener("pointerup", finishLayoutDrag);
  svg.addEventListener("pointercancel", finishLayoutDrag);
  svg.addEventListener("keydown", onLayoutKeyDown);
  root.querySelector("[data-sf-action='edit-layout']")?.addEventListener("click", () => setLayoutMode(!layoutMode));
  root.querySelector("[data-sf-action='undo-layout']")?.addEventListener("click", () => {
    const previous = layoutHistory.undo();
    if (!previous) return;
    styleState.layout = copyLayout(previous);
    applyLayout();
    syncLayoutInspector();
    stateStore.save(styleState);
    status.textContent = "Last layout move undone.";
  });
  root.querySelector("[data-sf-action='restore-style']")?.addEventListener("click", () => {
    styleState = {...defaults, markerSizes: {...defaults.markerSizes}, layout: copyLayout(defaults.layout)};
    automaticTopLayout = true;
    layoutHistory.clear();
    stateStore.clear();
    applyStyle({persist: false});
    status.textContent = "Default presentation style restored.";
  });
  root.querySelector("[data-sf-action='export-svg']")?.addEventListener("click", downloadSvg);

  applyStyle({persist: false});
  controller.setView(embeddedState?.view || fullView, "initial");
  root.dataset.sfRenderer = data.renderer;
  function getState() {
    return structuredClone({version: 1, figureId: data.figureId, style: styleState, view: controller.getView(), pointerMode: controller.getPointerMode()});
  }
  function serializeHtml() {
    const doc = new DOMParser().parseFromString(originalDocument, "text/html");
    doc.getElementById("scientific-figure-state")?.remove();
    const state = doc.createElement("script");
    state.id = "scientific-figure-state"; state.type = "application/json";
    state.textContent = JSON.stringify(getState()).replace(/</g, "\\u003c");
    doc.head.append(state);
    return "<!doctype html>\n" + doc.documentElement.outerHTML;
  }
  function exportCurrentSvg() {
    const clean = ScientificFigureRuntime.sanitizeSvg(svg);
    clean.querySelectorAll('[style*="display: none"], [data-sf-layout-hit]').forEach(el => {
      // Matplotlib places marker definitions in a series group; legends can reuse them.
      el.querySelectorAll('defs').forEach(defs => clean.prepend(defs));
      el.remove();
    });
    clean.querySelectorAll("*").forEach(el => {
      el.removeAttribute("data-sf-selected");
      el.style?.removeProperty("filter");
    });
    const model = structuredClone(data.figureModel);
    model.series.forEach((series, index) => {
      series.points = data.series[index].x.map((x, i) => [x, data.series[index].y[i]]);
    });
    model.presentation.currentState = getState();
    model.x.domain = [controller.getView().xMin, controller.getView().xMax];
    model.y.domain = [controller.getView().yMin, controller.getView().yMax];
    model.x.title = styleState.xLabel; model.y.title = styleState.yLabel;
    model.x.ticks = ticksForAxis("x", ...model.x.domain); model.y.ticks = ticksForAxis("y", ...model.y.domain);
    clean.querySelectorAll("metadata").forEach(el => el.remove());
    const metadata = node("metadata", {"data-role": "figure-model"}, JSON.stringify(model));
    const conversion = node("g", {"data-role": "point-to-mm-conversion", transform: "scale(0.3527777777777778)"});
    while (clean.firstChild) conversion.appendChild(clean.firstChild);
    clean.append(metadata, conversion);
    clean.setAttribute("data-role", "scientific-figure");
    clean.setAttribute("data-profile", model.profile);
    clean.setAttribute("data-source-origin", "authoritative-data");
    clean.setAttribute("data-coordinate-confidence", "exact");
    clean.setAttribute("data-user-unit-mm", "1");
    clean.setAttribute("data-physical-coordinate-system", "mm-isomorphic");
    clean.setAttribute("width", `${profile.exportWidthMm}mm`);
    clean.setAttribute("height", `${profile.exportHeightMm}mm`);
    clean.setAttribute("viewBox", `0 0 ${profile.exportWidthMm} ${profile.exportHeightMm}`);
    clean.setAttribute("data-export-state", "current");
    const roles = {"sf-dynamic-geometry": "plot-area", "sf-dynamic-ticks": "axes", "sf-x-axis-label": "axis-title-x", "sf-y-axis-label": "axis-title-y", "sf-legend": "legend"};
    for (const [id, role] of Object.entries(roles)) clean.querySelector(`#${id}`)?.setAttribute("data-role", role);
    clean.querySelector("#axes_1 > g[id^='patch_']")?.setAttribute("data-role", "plot-box");
    clean.querySelectorAll("circle[data-sf-series-id]").forEach(el => {el.setAttribute("data-role", "data-series"); el.setAttribute("data-series-id", el.dataset.sfSeriesId);});
    const style = node("style", {}, `svg{--figure-font-family:Calibri,"Microsoft YaHei",sans-serif;--axis-label-size:${styleState.axisFontPt}px;--tick-label-size:${styleState.plotFontPt}px;--annotation-size:${profile.legendPt}px;--data-line-width:${styleState.lineWidthPt}px;--axis-line-width:${profile.axisWidthPt}px;--tick-length:${Math.max(2.5, profile.axisWidthPt * 4.5)}px}`);
    clean.prepend(style);
    for (const id of ['sf-x-axis-label', 'sf-y-axis-label']) {
      clean.querySelector(`#${id} text`)?.style.setProperty('font-size', 'var(--axis-label-size)');
    }
    clean.querySelector('#sf-dynamic-ticks')?.setAttribute('font-size', 'var(--tick-label-size)');
    // Keep independent exports safely composable without cross-figure id collisions.
    const idMap = new Map([...clean.querySelectorAll('[id]')].map(el => [el.id, `${data.figureId}-${el.id}`]));
    for (const element of clean.querySelectorAll('*')) {
      if (element.id) element.id = idMap.get(element.id);
      for (const attribute of [...element.attributes]) {
        let value = attribute.value.replace(/url\(#([^\)]+)\)/g, (match, id) => `url(#${idMap.get(id) || id})`);
        if (attribute.localName === 'href' && value.startsWith('#')) value = `#${idMap.get(value.slice(1)) || value.slice(1)}`;
        attribute.value = value;
      }
    }
    clean.id = data.figureId;
    return new XMLSerializer().serializeToString(clean);
  }
  window.ScientificFigure = Object.freeze({version: 1, getState, serializeHtml, exportCurrentSvg,
    setView(view) { controller.setView(view, "user"); },
    ready: document.fonts.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => {
      placeAxisTitles(); root.dataset.sfReady = "true"; resolve();
    })))),
  });
  new ResizeObserver(() => requestAnimationFrame(placeAxisTitles)).observe(svg);
  root.querySelector('[data-sf-action="save-html"]')?.addEventListener("click", () => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([serializeHtml()], {type: "text/html"}));
    link.download = `${data.figureId}.html`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0);
  });
})();
