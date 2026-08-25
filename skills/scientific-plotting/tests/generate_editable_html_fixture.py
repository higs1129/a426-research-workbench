"""Generate a deterministic standalone editable scientific-figure HTML fixture."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Editable scientific figure fixture</title>
<style>
  :root { color-scheme: light; font-family: Calibri, "Microsoft YaHei", sans-serif; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px; background: #f4f6f8; color: #17191c; }
  main { max-width: 1120px; margin: 0 auto; }
  h1 { margin: 0 0 6px; font-size: 22px; }
  .lede { margin: 0 0 18px; color: #4b5563; }
  .workspace { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 20px; align-items: start; }
  .figure-card, .editor { background: white; border: 1px solid #d9dde3; border-radius: 10px; box-shadow: 0 2px 8px rgb(0 0 0 / 6%); }
  .figure-card { padding: 16px; overflow: auto; }
  #figure-wrap { width: min(100%, 700px); margin: 0 auto; }
  #chart { display: block; width: 100%; height: auto; background: white; touch-action: none; user-select: none; }
  #chart text { fill: #000; }
  #interaction-surface { fill: transparent; cursor: crosshair; }
  #interaction-surface.pan-mode { cursor: grab; }
  #interaction-surface.pan-mode.dragging { cursor: grabbing; }
  .inspection-toolbar { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin: 0 auto 10px; }
  #hover-readout { flex: 1 1 260px; min-height: 30px; padding: 6px 9px; border: 1px solid #c9ced6; border-radius: 6px; background: #f8fafc; color: #111; font-size: 13px; font-variant-numeric: tabular-nums; }
  .mode-button[aria-pressed="true"] { background: #174f78; border-color: #174f78; color: #fff; }
  .gesture-hint { flex: 1 1 100%; margin: 0; color: #3f4853; font-size: 12px; }
  .editor { padding: 16px; }
  .editor h2 { margin: 0 0 14px; font-size: 17px; }
  .control { display: grid; gap: 5px; margin-bottom: 12px; }
  .control label { font-size: 13px; font-weight: 700; }
  .control output { color: #445; font-weight: 400; }
  input, select, button { font: inherit; }
  input[type="text"], select { width: 100%; padding: 7px 8px; border: 1px solid #b8bec8; border-radius: 6px; }
  input[type="range"] { width: 100%; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
  button { padding: 7px 10px; border: 1px solid #9ba3ad; border-radius: 6px; background: #fff; cursor: pointer; }
  button:hover, button:focus-visible { background: #eef3f8; }
  #status { min-height: 1.4em; margin: 12px 0 0; font-size: 12px; color: #315b44; }
  .source-note { margin: 12px 0 0; font-size: 12px; color: #5f6670; }
  @media (max-width: 760px) {
    body { padding: 12px; }
    .workspace { grid-template-columns: 1fr; }
    .editor { order: 2; }
  }
</style>
</head>
<body>
<main>
  <h1>Editable 90 mm scientific-figure profile</h1>
  <p class="lede">Synthetic resonance data; responsive screen view with a 90 mm SVG export baseline.</p>
  <div class="workspace">
    <section class="figure-card" aria-label="Editable scientific figure">
      <div id="figure-wrap">
        <div class="inspection-toolbar" aria-label="Figure inspection controls">
          <button id="box-zoom-mode" class="mode-button" type="button" aria-pressed="true">Box zoom</button>
          <button id="pan-mode" class="mode-button" type="button" aria-pressed="false">Pan</button>
          <button id="zoom-in" type="button" aria-label="Zoom in">Zoom +</button>
          <button id="zoom-out" type="button" aria-label="Zoom out">Zoom −</button>
          <button id="reset-view" type="button">Reset view</button>
          <output id="hover-readout" aria-live="polite">Hover over the curve to inspect a raw value.</output>
          <p id="gesture-hint" class="gesture-hint">Box zoom: drag a rectangle with the left mouse button. Wheel zoom is always available.</p>
        </div>
        <svg id="chart" viewBox="0 0 340 220" role="img" aria-labelledby="chart-title chart-desc">
          <title id="chart-title">Synthetic resonance response</title>
          <desc id="chart-desc">Raw synthetic measurements with a fitted Lorentzian guide. Hover to inspect exact values, wheel to zoom, drag a box to zoom both axes, or choose Pan and drag to move both axes.</desc>
          <defs><clipPath id="plot-clip"><rect x="47" y="25" width="279" height="159"/></clipPath></defs>
          <rect x="0" y="0" width="340" height="220" fill="white"/>
          <g id="axes"></g>
          <g id="data-layer" clip-path="url(#plot-clip)">
            <polyline id="raw-line" fill="none" stroke-linejoin="round" stroke-linecap="round"></polyline>
            <polyline id="fit-line" fill="none" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="5 3"></polyline>
            <g id="markers"></g>
            <g id="hover-crosshair" pointer-events="none" visibility="hidden">
              <line id="hover-guide-x" stroke="#217565" stroke-width="1.4" stroke-dasharray="5 4"></line>
              <line id="hover-guide-y" stroke="#217565" stroke-width="1.4" stroke-dasharray="5 4"></line>
              <circle id="hover-point" r="4.2" fill="#217565" stroke="white" stroke-width="1.2"></circle>
            </g>
          </g>
          <g id="hover-tooltip" pointer-events="none" visibility="hidden">
            <rect id="hover-tooltip-box" width="102" height="32" rx="3" fill="white" fill-opacity="0.96" stroke="#217565"></rect>
            <text id="hover-tooltip-series" font-weight="700">Raw data</text>
            <text id="hover-tooltip-value"></text>
          </g>
          <rect id="box-zoom-rect" visibility="hidden" fill="#2468a2" fill-opacity="0.12" stroke="#2468a2" stroke-width="1" stroke-dasharray="4 3" pointer-events="none"></rect>
          <g id="legend" transform="translate(224 31)">
            <rect x="0" y="0" width="87" height="31" rx="2" fill="white" fill-opacity="0.9" stroke="#a8adb5"/>
            <line id="legend-raw-line" x1="7" y1="10" x2="25" y2="10"/>
            <text id="legend-raw" x="30" y="12.5" fill="#000">Raw data</text>
            <line id="legend-fit-line" x1="7" y1="22" x2="25" y2="22" stroke-dasharray="5 3"/>
            <text id="legend-fit" x="30" y="24.5" fill="#000">Fit guide</text>
          </g>
          <text id="plot-title" x="177" y="17" text-anchor="middle" fill="#000"></text>
          <text id="x-label" x="177" y="212" text-anchor="middle" fill="#000"></text>
          <text id="y-label" x="12" y="108" text-anchor="middle" fill="#000" transform="rotate(-90 12 108)"></text>
          <rect id="interaction-surface" x="47" y="25" width="279" height="159" tabindex="0" role="application" aria-label="Interactive plot area. Hover for exact values. In Box zoom mode, left-drag a rectangle to zoom both axes. In Pan mode, left-drag to move both axes. Wheel zoom is always available."></rect>
        </svg>
      </div>
      <p class="source-note">Source: deterministic synthetic fixture; exact peak claims are not used as scientific evidence.</p>
    </section>

    <aside class="editor" aria-label="Figure style editor">
      <h2>Figure editor</h2>
      <div class="control"><label for="title-input">Title</label><input id="title-input" type="text"></div>
      <div class="control"><label for="x-label-input">X-axis label</label><input id="x-label-input" type="text"></div>
      <div class="control"><label for="y-label-input">Y-axis label</label><input id="y-label-input" type="text"></div>
      <div class="control"><label for="font-family">Font family</label><select id="font-family"><option value='Calibri, "Microsoft YaHei", sans-serif'>Calibri + Microsoft YaHei</option><option value='Arial, "Microsoft YaHei", sans-serif'>Arial + Microsoft YaHei</option></select></div>
      <div class="control"><label for="font-size">Tick/legend font: <output id="font-size-value"></output></label><input id="font-size" type="range" min="6" max="12" step="0.5"></div>
      <div class="control"><label for="raw-width">Raw line: <output id="raw-width-value"></output></label><input id="raw-width" type="range" min="0.5" max="3" step="0.1"></div>
      <div class="control"><label for="fit-width">Fit line: <output id="fit-width-value"></output></label><input id="fit-width" type="range" min="0.5" max="3" step="0.1"></div>
      <div class="control"><label for="axis-width">Axis line: <output id="axis-width-value"></output></label><input id="axis-width" type="range" min="0.4" max="2" step="0.1"></div>
      <div class="control"><label for="marker-size">Marker diameter: <output id="marker-size-value"></output></label><input id="marker-size" type="range" min="2" max="9" step="0.5"></div>
      <div class="control"><label for="screen-width">Screen width: <output id="screen-width-value"></output></label><input id="screen-width" type="range" min="420" max="850" step="10"></div>
      <div class="control"><label for="raw-color">Raw color</label><input id="raw-color" type="color"></div>
      <div class="actions">
        <button id="reset" type="button">Reset all</button>
        <button id="download-state" type="button">Download state</button>
        <button id="export-svg" type="button">Export SVG</button>
      </div>
      <p id="status" role="status"></p>
    </aside>
  </div>
</main>
<script>
const data = __DATA__;
const initialState = Object.freeze({
  title: "Synthetic resonance response",
  xLabel: "Frequency (kHz)",
  yLabel: "Normalized response",
  fontFamily: 'Calibri, "Microsoft YaHei", sans-serif',
  fontPt: 7,
  axisLabelPt: 8,
  titlePt: 9,
  rawWidthPt: 1.0,
  fitWidthPt: 0.8,
  axisWidthPt: 0.8,
  markerPt: 4.5,
  rawColor: "#2468a2",
  fitColor: "#c03a3a",
  screenWidth: 700,
  xMin: 0,
  xMax: 100,
  yMin: 0,
  yMax: 1.2,
  interactionMode: "zoom"
});
let state = {...initialState};
let hoverIndex = null;
const PT_TO_UNIT = 96 / 72;
const NS = "http://www.w3.org/2000/svg";
const plot = {left: 47, right: 326, top: 25, bottom: 184, fullXMin: 0, fullXMax: 100, fullYMin: 0, fullYMax: 1.2};

function sx(x) { return plot.left + (x - state.xMin) / (state.xMax - state.xMin) * (plot.right - plot.left); }
function sy(y) { return plot.bottom - (y - state.yMin) / (state.yMax - state.yMin) * (plot.bottom - plot.top); }
function ix(px) { return state.xMin + (px - plot.left) / (plot.right - plot.left) * (state.xMax - state.xMin); }
function iy(py) { return state.yMin + (plot.bottom - py) / (plot.bottom - plot.top) * (state.yMax - state.yMin); }
function points(values) { return values.map(d => `${sx(d.x).toFixed(2)},${sy(d.y).toFixed(2)}`).join(" "); }
function svgEl(name, attrs = {}) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}
function setText(id, value) { document.getElementById(id).textContent = value; }

function ticks(minimum, maximum, count) {
  return Array.from({length: count}, (_, index) => minimum + index * (maximum - minimum) / (count - 1));
}

function formatTick(value, span) {
  if (span < 1) return value.toFixed(2);
  if (span < 10) return value.toFixed(1);
  return value.toFixed(0);
}

function clampView() {
  const clampRange = (minimum, maximum, fullMinimum, fullMaximum, minSpan) => {
    const fullSpan = fullMaximum - fullMinimum;
    const span = Math.min(fullSpan, Math.max(minSpan, maximum - minimum));
    const nextMinimum = Math.max(fullMinimum, Math.min(minimum, fullMaximum - span));
    return [nextMinimum, nextMinimum + span];
  };
  [state.xMin, state.xMax] = clampRange(state.xMin, state.xMax, plot.fullXMin, plot.fullXMax, 2);
  [state.yMin, state.yMax] = clampRange(state.yMin, state.yMax, plot.fullYMin, plot.fullYMax, 0.04);
}

function zoomAt(factor, px = (plot.left + plot.right) / 2, py = (plot.top + plot.bottom) / 2) {
  const anchorX = ix(px);
  const anchorY = iy(py);
  state.xMin = anchorX - (anchorX - state.xMin) * factor;
  state.xMax = anchorX + (state.xMax - anchorX) * factor;
  state.yMin = anchorY - (anchorY - state.yMin) * factor;
  state.yMax = anchorY + (state.yMax - anchorY) * factor;
  clampView();
  render();
}

function panBySvg(dx, dy) {
  const dataDx = dx / (plot.right - plot.left) * (state.xMax - state.xMin);
  const dataDy = dy / (plot.bottom - plot.top) * (state.yMax - state.yMin);
  state.xMin -= dataDx;
  state.xMax -= dataDx;
  state.yMin += dataDy;
  state.yMax += dataDy;
  clampView();
  render();
}

function resetView() {
  state.xMin = initialState.xMin;
  state.xMax = initialState.xMax;
  state.yMin = initialState.yMin;
  state.yMax = initialState.yMax;
  hoverIndex = null;
  render();
}

function hoverNearestAt(px, py) {
  let nearestIndex = null;
  let nearestDistance = Infinity;
  data.raw.forEach((point, index) => {
    if (point.x < state.xMin || point.x > state.xMax || point.y < state.yMin || point.y > state.yMax) return;
    const distance = Math.hypot(sx(point.x) - px, sy(point.y) - py);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });
  hoverIndex = nearestIndex;
  drawHover();
}

function clearHover() {
  hoverIndex = null;
  drawHover();
}

function setInteractionMode(mode) {
  if (mode !== "zoom" && mode !== "pan") return;
  state.interactionMode = mode;
  clearHover();
  renderInteractionMode();
}

function applyBoxZoom(x0, y0, x1, y1) {
  const left = Math.max(plot.left, Math.min(x0, x1));
  const right = Math.min(plot.right, Math.max(x0, x1));
  const top = Math.max(plot.top, Math.min(y0, y1));
  const bottom = Math.min(plot.bottom, Math.max(y0, y1));
  if (right - left < 5 || bottom - top < 5) return false;
  const nextXMin = ix(left);
  const nextXMax = ix(right);
  const nextYMin = iy(bottom);
  const nextYMax = iy(top);
  state.xMin = nextXMin;
  state.xMax = nextXMax;
  state.yMin = nextYMin;
  state.yMax = nextYMax;
  clampView();
  clearHover();
  render();
  return true;
}

function drawAxes() {
  const axes = document.getElementById("axes");
  axes.replaceChildren();
  const axisStroke = state.axisWidthPt * PT_TO_UNIT;
  const box = svgEl("rect", {x: plot.left, y: plot.top, width: plot.right - plot.left, height: plot.bottom - plot.top, fill: "none", stroke: "#111", "stroke-width": axisStroke});
  axes.appendChild(box);
  const xSpan = state.xMax - state.xMin;
  const ySpan = state.yMax - state.yMin;
  for (const x of ticks(state.xMin, state.xMax, 6)) {
    const px = sx(x);
    axes.appendChild(svgEl("line", {x1: px, y1: plot.bottom, x2: px, y2: plot.bottom + 4, stroke: "#111", "stroke-width": axisStroke}));
    const label = svgEl("text", {x: px, y: plot.bottom + 13, "text-anchor": "middle", fill: "#000"});
    label.textContent = formatTick(x, xSpan);
    axes.appendChild(label);
  }
  for (const y of ticks(state.yMin, state.yMax, 5)) {
    const py = sy(y);
    axes.appendChild(svgEl("line", {x1: plot.left - 4, y1: py, x2: plot.left, y2: py, stroke: "#111", "stroke-width": axisStroke}));
    const label = svgEl("text", {x: plot.left - 7, y: py + 3, "text-anchor": "end", fill: "#000"});
    label.textContent = formatTick(y, ySpan);
    axes.appendChild(label);
  }
}

function drawMarkers() {
  const markers = document.getElementById("markers");
  markers.replaceChildren();
  const radius = state.markerPt * PT_TO_UNIT / 2;
  data.raw.filter((_, i) => i % 10 === 0).forEach(d => {
    markers.appendChild(svgEl("circle", {cx: sx(d.x), cy: sy(d.y), r: radius, fill: "white", stroke: state.rawColor, "stroke-width": 0.8 * PT_TO_UNIT}));
  });
}

function drawHover() {
  const crosshair = document.getElementById("hover-crosshair");
  const tooltip = document.getElementById("hover-tooltip");
  if (hoverIndex === null) {
    crosshair.setAttribute("visibility", "hidden");
    tooltip.setAttribute("visibility", "hidden");
    setText("hover-readout", "Hover over the curve to inspect a raw value.");
    return;
  }
  const point = data.raw[hoverIndex];
  const visible = point.x >= state.xMin && point.x <= state.xMax && point.y >= state.yMin && point.y <= state.yMax;
  if (!visible) {
    clearHover();
    return;
  }
  const px = sx(point.x);
  const py = sy(point.y);
  const vertical = document.getElementById("hover-guide-x");
  const horizontal = document.getElementById("hover-guide-y");
  vertical.setAttribute("x1", px); vertical.setAttribute("x2", px);
  vertical.setAttribute("y1", plot.top); vertical.setAttribute("y2", plot.bottom);
  horizontal.setAttribute("x1", plot.left); horizontal.setAttribute("x2", plot.right);
  horizontal.setAttribute("y1", py); horizontal.setAttribute("y2", py);
  const marker = document.getElementById("hover-point");
  marker.setAttribute("cx", px); marker.setAttribute("cy", py);
  const tooltipX = px > (plot.left + plot.right) / 2 ? px - 108 : px + 7;
  const tooltipY = Math.max(plot.top + 2, Math.min(py - 36, plot.bottom - 34));
  document.getElementById("hover-tooltip-box").setAttribute("x", tooltipX);
  document.getElementById("hover-tooltip-box").setAttribute("y", tooltipY);
  const series = document.getElementById("hover-tooltip-series");
  series.setAttribute("x", tooltipX + 6); series.setAttribute("y", tooltipY + 12);
  const value = document.getElementById("hover-tooltip-value");
  value.setAttribute("x", tooltipX + 6); value.setAttribute("y", tooltipY + 25);
  value.textContent = `x ${point.x.toFixed(3)}; y ${point.y.toFixed(6)}`;
  crosshair.setAttribute("visibility", "visible");
  tooltip.setAttribute("visibility", "visible");
  setText("hover-readout", `Raw data — Frequency: ${point.x.toFixed(3)} kHz; response: ${point.y.toFixed(6)}`);
}

function renderInteractionMode() {
  const isZoom = state.interactionMode === "zoom";
  document.getElementById("box-zoom-mode").setAttribute("aria-pressed", String(isZoom));
  document.getElementById("pan-mode").setAttribute("aria-pressed", String(!isZoom));
  document.getElementById("interaction-surface").classList.toggle("pan-mode", !isZoom);
  setText("gesture-hint", isZoom
    ? "Box zoom: drag a rectangle with the left mouse button. Wheel zoom is always available."
    : "Pan: drag with the left mouse button to move both axes. Wheel zoom is always available.");
}

function render() {
  document.getElementById("figure-wrap").style.width = `min(100%, ${state.screenWidth}px)`;
  const chart = document.getElementById("chart");
  chart.style.fontFamily = state.fontFamily;
  chart.style.fontSize = `${state.fontPt * PT_TO_UNIT}px`;
  drawAxes();
  const raw = document.getElementById("raw-line");
  raw.setAttribute("points", points(data.raw));
  raw.setAttribute("stroke", state.rawColor);
  raw.setAttribute("stroke-width", state.rawWidthPt * PT_TO_UNIT);
  raw.setAttribute("opacity", "0.58");
  const fit = document.getElementById("fit-line");
  fit.setAttribute("points", points(data.fit));
  fit.setAttribute("stroke", state.fitColor);
  fit.setAttribute("stroke-width", state.fitWidthPt * PT_TO_UNIT);
  drawMarkers();
  drawHover();
  renderInteractionMode();
  setText("plot-title", state.title);
  setText("chart-title", state.title);
  setText("x-label", state.xLabel);
  setText("y-label", state.yLabel);
  document.getElementById("plot-title").style.fontSize = `${state.titlePt * PT_TO_UNIT}px`;
  document.getElementById("plot-title").style.fontWeight = "700";
  for (const id of ["x-label", "y-label"]) {
    document.getElementById(id).style.fontSize = `${state.axisLabelPt * PT_TO_UNIT}px`;
    document.getElementById(id).style.fontWeight = "700";
  }
  for (const id of ["legend-raw-line", "legend-fit-line"]) {
    document.getElementById(id).setAttribute("stroke", id.includes("raw") ? state.rawColor : state.fitColor);
    document.getElementById(id).setAttribute("stroke-width", (id.includes("raw") ? state.rawWidthPt : state.fitWidthPt) * PT_TO_UNIT);
  }
  syncControls();
}

function bindRange(id, key, suffix) {
  const input = document.getElementById(id);
  input.addEventListener("input", () => { state[key] = Number(input.value); render(); });
  return () => { input.value = state[key]; setText(`${id}-value`, `${state[key]}${suffix}`); };
}
const syncers = [
  bindRange("font-size", "fontPt", " pt"),
  bindRange("raw-width", "rawWidthPt", " pt"),
  bindRange("fit-width", "fitWidthPt", " pt"),
  bindRange("axis-width", "axisWidthPt", " pt"),
  bindRange("marker-size", "markerPt", " pt"),
  bindRange("screen-width", "screenWidth", " px")
];
function bindText(id, key) { document.getElementById(id).addEventListener("input", e => { state[key] = e.target.value; render(); }); }
bindText("title-input", "title");
bindText("x-label-input", "xLabel");
bindText("y-label-input", "yLabel");
document.getElementById("font-family").addEventListener("change", e => { state.fontFamily = e.target.value; render(); });
document.getElementById("raw-color").addEventListener("input", e => { state.rawColor = e.target.value; render(); });

function syncControls() {
  document.getElementById("title-input").value = state.title;
  document.getElementById("x-label-input").value = state.xLabel;
  document.getElementById("y-label-input").value = state.yLabel;
  document.getElementById("font-family").value = state.fontFamily;
  document.getElementById("raw-color").value = state.rawColor;
  syncers.forEach(sync => sync());
}

function clientToSvg(event) {
  const chart = document.getElementById("chart");
  const bounds = chart.getBoundingClientRect();
  return {
    x: (event.clientX - bounds.left) / bounds.width * 340,
    y: (event.clientY - bounds.top) / bounds.height * 220,
  };
}

const surface = document.getElementById("interaction-surface");
let dragState = null;
surface.addEventListener("wheel", event => {
  event.preventDefault();
  const point = clientToSvg(event);
  zoomAt(event.deltaY < 0 ? 0.82 : 1.22, point.x, point.y);
});
surface.addEventListener("pointerdown", event => {
  if (event.button !== undefined && event.button !== 0) return;
  event.preventDefault();
  const point = clientToSvg(event);
  dragState = {mode: state.interactionMode, startX: point.x, startY: point.y, lastX: point.x, lastY: point.y, moved: false};
  clearHover();
  surface.classList.add("dragging");
  surface.setPointerCapture?.(event.pointerId);
});
surface.addEventListener("pointermove", event => {
  const point = clientToSvg(event);
  if (!dragState) {
    if (event.pointerType !== "touch") hoverNearestAt(point.x, point.y);
    return;
  }
  event.preventDefault();
  const dx = point.x - dragState.lastX;
  const dy = point.y - dragState.lastY;
  if (Math.hypot(point.x - dragState.startX, point.y - dragState.startY) > 3) dragState.moved = true;
  dragState.lastX = point.x;
  dragState.lastY = point.y;
  if (!dragState.moved) return;
  if (dragState.mode === "pan") {
    panBySvg(dx, dy);
  } else {
    const brush = document.getElementById("box-zoom-rect");
    const x = Math.max(plot.left, Math.min(dragState.startX, point.x));
    const y = Math.max(plot.top, Math.min(dragState.startY, point.y));
    const right = Math.min(plot.right, Math.max(dragState.startX, point.x));
    const bottom = Math.min(plot.bottom, Math.max(dragState.startY, point.y));
    brush.setAttribute("x", x); brush.setAttribute("y", y);
    brush.setAttribute("width", Math.max(0, right - x)); brush.setAttribute("height", Math.max(0, bottom - y));
    brush.setAttribute("visibility", "visible");
  }
});
function finishPointer(event) {
  if (!dragState) return;
  const point = clientToSvg(event);
  if (dragState.mode === "zoom" && dragState.moved) {
    applyBoxZoom(dragState.startX, dragState.startY, point.x, point.y);
  } else if (!dragState.moved) {
    hoverNearestAt(point.x, point.y);
  }
  dragState = null;
  document.getElementById("box-zoom-rect").setAttribute("visibility", "hidden");
  surface.classList.remove("dragging");
}
surface.addEventListener("pointerup", finishPointer);
surface.addEventListener("pointercancel", () => {
  dragState = null;
  document.getElementById("box-zoom-rect").setAttribute("visibility", "hidden");
  surface.classList.remove("dragging");
});
surface.addEventListener("pointerleave", () => { if (!dragState) clearHover(); });
surface.addEventListener("keydown", event => {
  if (event.key === "+" || event.key === "=") zoomAt(0.82);
  else if (event.key === "-") zoomAt(1.22);
  else if (event.key === "ArrowLeft") panBySvg(-12, 0);
  else if (event.key === "ArrowRight") panBySvg(12, 0);
  else if (event.key === "ArrowUp") panBySvg(0, -12);
  else if (event.key === "ArrowDown") panBySvg(0, 12);
  else if (event.key === "Enter") hoverNearestAt((plot.left + plot.right) / 2, (plot.top + plot.bottom) / 2);
  else if (event.key === "Escape") clearHover();
  else return;
  event.preventDefault();
});

document.getElementById("box-zoom-mode").addEventListener("click", () => { setInteractionMode("zoom"); setText("status", "Box zoom mode: left-drag a rectangle to zoom both axes."); });
document.getElementById("pan-mode").addEventListener("click", () => { setInteractionMode("pan"); setText("status", "Pan mode: left-drag to move both axes."); });
document.getElementById("zoom-in").addEventListener("click", () => zoomAt(0.82));
document.getElementById("zoom-out").addEventListener("click", () => zoomAt(1.22));
document.getElementById("reset-view").addEventListener("click", () => { clearHover(); resetView(); setText("status", "Full view restored."); });

function download(name, type, content) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.getElementById("reset").addEventListener("click", () => { state = {...initialState}; hoverIndex = null; render(); setText("status", "Defaults restored."); });
document.getElementById("download-state").addEventListener("click", () => { download("figure-state.json", "application/json", JSON.stringify({profile: "90mm-publication", state, data}, null, 2)); setText("status", "State downloaded."); });
document.getElementById("export-svg").addEventListener("click", () => {
  const copy = document.getElementById("chart").cloneNode(true);
  const transientIds = ["hover-crosshair", "hover-tooltip", "box-zoom-rect", "interaction-surface"];
  for (const id of transientIds) copy.querySelector?.(`#${id}`)?.setAttribute("visibility", "hidden");
  copy.setAttribute("xmlns", NS);
  copy.setAttribute("width", "90mm");
  copy.setAttribute("height", "58.24mm");
  download("synthetic-resonance.svg", "image/svg+xml", new XMLSerializer().serializeToString(copy));
  setText("status", "90 mm SVG exported.");
});
window.__figureTest = {
  getState: () => ({...state}),
  setState: patch => { state = {...state, ...patch}; render(); },
  getSvg: () => document.getElementById("chart"),
  zoomAt,
  panBySvg,
  hoverNearestAt,
  clearHover,
  setInteractionMode,
  applyBoxZoom,
  getHoverIndex: () => hoverIndex,
  resetView,
};
render();
</script>
</body>
</html>
"""


def build_data() -> dict[str, list[dict[str, float]]]:
    raw: list[dict[str, float]] = []
    fit: list[dict[str, float]] = []
    for index in range(101):
        frequency = float(index)
        fitted = 0.12 + 0.94 / (1.0 + ((frequency - 52.0) / 11.5) ** 2)
        measured = fitted + 0.028 * math.sin(frequency * 0.63) + 0.012 * math.sin(frequency * 1.77)
        fit.append({"x": frequency, "y": round(fitted, 6)})
        raw.append({"x": frequency, "y": round(measured, 6)})
    return {"raw": raw, "fit": fit}


def render_preview(
    data: dict[str, list[dict[str, float]]], output: Path, hover_index: int | None = None
) -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 7,
            "font.family": ["Calibri", "Microsoft YaHei"],
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "axes.titlecolor": "black",
            "axes.labelcolor": "black",
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "xtick.color": "black",
            "ytick.color": "black",
            "legend.fontsize": 7,
            "legend.labelcolor": "black",
            "text.color": "black",
            "lines.linewidth": 1.0,
            "axes.grid": False,
            "savefig.dpi": 300,
        }
    )
    mm_to_in = lambda mm: mm / 25.4
    figure, axis = plt.subplots(
        figsize=(mm_to_in(90), mm_to_in(58.24)), constrained_layout=True
    )
    axis.plot(
        [item["x"] for item in data["raw"]],
        [item["y"] for item in data["raw"]],
        color="#2468a2",
        alpha=0.58,
        label="Raw data",
    )
    axis.plot(
        [item["x"] for item in data["fit"]],
        [item["y"] for item in data["fit"]],
        color="#c03a3a",
        linewidth=0.8,
        linestyle="--",
        label="Fit guide",
    )
    selected = data["raw"][::10]
    axis.plot(
        [item["x"] for item in selected],
        [item["y"] for item in selected],
        linestyle="none",
        marker="o",
        markersize=4.5,
        markerfacecolor="white",
        markeredgecolor="#2468a2",
        markeredgewidth=0.8,
    )
    axis.set(
        title="Synthetic resonance response",
        xlabel="Frequency (kHz)",
        ylabel="Normalized response",
        xlim=(0, 100),
        ylim=(0, 1.2),
    )
    axis.tick_params(direction="out", width=0.8)
    for spine in axis.spines.values():
        spine.set_linewidth(0.8)
    axis.legend(frameon=True, loc="upper right")
    if hover_index is not None:
        point = data["raw"][hover_index]
        axis.axvline(point["x"], color="#217565", linewidth=1.05, linestyle=(0, (5, 4)))
        axis.axhline(point["y"], color="#217565", linewidth=1.05, linestyle=(0, (5, 4)))
        axis.plot(
            point["x"],
            point["y"],
            linestyle="none",
            marker="o",
            markersize=6.2,
            markerfacecolor="#217565",
            markeredgecolor="white",
            markeredgewidth=0.9,
            zorder=5,
        )
        axis.annotate(
            f"Raw data\nx {point['x']:.3f}; y {point['y']:.6f}",
            xy=(point["x"], point["y"]),
            xytext=(-88, -38),
            textcoords="offset points",
            fontsize=7,
            color="black",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#217565", "alpha": 0.96},
        )
    figure.savefig(output)
    plt.close(figure)


def main() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=fixture_dir / "editable-resonance.html"
    )
    parser.add_argument(
        "--preview-png", type=Path, default=fixture_dir / "profile-preview.png"
    )
    parser.add_argument(
        "--interaction-preview-png",
        type=Path,
        default=fixture_dir / "hover-preview.png",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data = build_data()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    output.write_text(HTML_TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    print(output)
    if args.preview_png:
        preview = args.preview_png.resolve()
        preview.parent.mkdir(parents=True, exist_ok=True)
        render_preview(data, preview)
        print(preview)
    if args.interaction_preview_png:
        interaction_preview = args.interaction_preview_png.resolve()
        interaction_preview.parent.mkdir(parents=True, exist_ok=True)
        render_preview(data, interaction_preview, hover_index=52)
        print(interaction_preview)


if __name__ == "__main__":
    main()
