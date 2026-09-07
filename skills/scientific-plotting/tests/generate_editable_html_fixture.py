"""Generate a deterministic standalone editable scientific-figure HTML fixture."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


PROFILE_PATH = Path(__file__).resolve().parents[1] / "assets" / "style-profiles.json"


def load_profiles() -> dict[str, dict[str, float | str]]:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def validate_profiles(profiles: dict[str, dict[str, float | str]]) -> None:
    required = {"90mm-single", "185mm-wide"}
    if set(profiles) != required:
        raise RuntimeError(f"Style profiles must be exactly {sorted(required)}")
    wide = profiles["185mm-wide"]
    expected = {
        "exportWidthMm": 185,
        "tickPt": 12,
        "axisLabelPt": 12,
        "legendPt": 12,
        "figureTitlePt": 10,
        "hoverTitlePt": 9,
        "hoverValuePt": 8,
        "axisTitleGapEmX": 0.3,
        "axisTitleGapEmY": 0.2,
    }
    for key, value in expected.items():
        if wide.get(key) != value:
            raise RuntimeError(f"185 mm profile requires {key}={value}")


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
  main { max-width: 1440px; margin: 0 auto; }
  h1 { margin: 0 0 6px; font-size: 22px; }
  .lede { margin: 0 0 18px; color: #4b5563; }
  .workspace { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 20px; align-items: start; }
  .workspace.editor-collapsed { grid-template-columns: minmax(0, 1fr); }
  .workspace.editor-collapsed .editor { display: none; }
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
  button:disabled { cursor: not-allowed; opacity: 0.45; }
  #chart.edit-layout #interaction-surface { pointer-events: none; }
  #chart:not(.edit-layout) .layout-editable { pointer-events: none; }
  #chart.edit-layout .layout-editable { cursor: move; pointer-events: auto; }
  #chart.edit-layout .layout-editable:focus { outline: none; filter: drop-shadow(0 0 3px #f59e0b); }
  #chart.edit-layout .layout-selected { filter: drop-shadow(0 0 4px #f59e0b); }
  #chart.edit-layout .scientific-locked { cursor: not-allowed; pointer-events: visiblePainted; }
  .gesture-hint { flex: 1 1 100%; margin: 0; color: #3f4853; font-size: 12px; }
  .editor { padding: 16px; }
  .editor h2 { margin: 0 0 14px; font-size: 17px; }
  .layout-inspector { margin: 0 0 16px; padding: 12px; border: 1px solid #f0b44d; border-radius: 8px; background: #fffaf0; }
  .layout-inspector[hidden] { display: none; }
  .layout-inspector h3 { margin: 0 0 7px; font-size: 15px; }
  .selected-name { margin: 0 0 10px; color: #9a5b00; font-size: 13px; font-weight: 700; }
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
  <h1>Editable scientific figure</h1>
  <p class="lede">Synthetic resonance data; the physical delivery profile is fixed when this HTML is generated.</p>
  <div class="workspace">
    <section class="figure-card" aria-label="Editable scientific figure">
      <div id="figure-wrap">
        <div class="inspection-toolbar" aria-label="Figure inspection controls">
          <button id="layout-edit-mode" class="mode-button" type="button" aria-pressed="false">Edit layout</button>
          <button id="toggle-editor-panel" type="button" aria-pressed="true">Hide editor</button>
          <button id="undo-edit" type="button" disabled>Undo edit</button>
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
            <polyline id="raw-line" class="scientific-locked" data-label="Raw data curve (locked)" fill="none" stroke-linejoin="round" stroke-linecap="round"></polyline>
            <polyline id="fit-line" class="scientific-locked" data-label="Fit guide (locked)" fill="none" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="5 3"></polyline>
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
          <g id="legend" class="layout-editable" data-layout-role="legend" data-label="Legend" tabindex="0" transform="translate(224 31)">
            <rect x="0" y="0" width="87" height="31" rx="2" fill="white" fill-opacity="0.9" stroke="#a8adb5"/>
            <line id="legend-raw-line" x1="7" y1="10" x2="25" y2="10"/>
            <text id="legend-raw" x="30" y="12.5" fill="#000">Raw data</text>
            <line id="legend-fit-line" x1="7" y1="22" x2="25" y2="22" stroke-dasharray="5 3"/>
            <text id="legend-fit" x="30" y="24.5" fill="#000">Fit guide</text>
          </g>
          <text id="plot-title" class="layout-editable" data-layout-role="title" data-label="Figure title" tabindex="0" x="177" y="17" text-anchor="middle" fill="#000"></text>
          <text id="x-label" class="layout-editable" data-layout-role="xLabel" data-label="X-axis title" tabindex="0" x="177" y="212" text-anchor="middle" fill="#000"></text>
          <text id="y-label" class="layout-editable" data-layout-role="yLabel" data-label="Y-axis title" tabindex="0" x="12" y="108" text-anchor="middle" fill="#000" transform="rotate(-90 12 108)"></text>
          <rect id="interaction-surface" x="47" y="25" width="279" height="159" tabindex="0" role="application" aria-label="Interactive plot area. Hover for exact values. In Box zoom mode, left-drag a rectangle to zoom both axes. In Pan mode, left-drag to move both axes. Wheel zoom is always available."></rect>
        </svg>
      </div>
      <p class="source-note">Source: deterministic synthetic fixture; exact peak claims are not used as scientific evidence.</p>
    </section>

    <aside class="editor" aria-label="Figure style editor">
      <h2>Figure editor</h2>
      <section id="layout-inspector" class="layout-inspector" hidden aria-label="Selected layout element">
        <h3>Selected layout element</h3>
        <p id="selected-layout-name" class="selected-name">Nothing selected</p>
        <div id="layout-text-row" class="control"><label for="layout-text">Text</label><input id="layout-text" type="text"></div>
        <div id="layout-font-row" class="control"><label for="layout-font-size">Font size (pt)</label><input id="layout-font-size" type="number" min="6" max="24" step="0.5"></div>
        <div class="control"><label for="layout-offset-x">Horizontal offset</label><input id="layout-offset-x" type="number" step="1"></div>
        <div class="control"><label for="layout-offset-y">Vertical offset</label><input id="layout-offset-y" type="number" step="1"></div>
        <button id="apply-layout-edit" class="apply" type="button">Apply selected element</button>
      </section>
      <div class="control"><label for="title-input">Title</label><input id="title-input" type="text"></div>
      <div class="control"><label for="x-label-input">X-axis label</label><input id="x-label-input" type="text"></div>
      <div class="control"><label for="y-label-input">Y-axis label</label><input id="y-label-input" type="text"></div>
      <div class="control"><label for="raw-legend-input">Raw-data legend</label><input id="raw-legend-input" type="text"></div>
      <div class="control"><label for="fit-legend-input">Fit-guide legend</label><input id="fit-legend-input" type="text"></div>
      <div class="control"><label for="font-family">Font family</label><select id="font-family"><option value='Calibri, "Microsoft YaHei", sans-serif'>Calibri + Microsoft YaHei</option><option value='Arial, "Microsoft YaHei", sans-serif'>Arial + Microsoft YaHei</option></select></div>
      <div class="control"><label for="font-size">Tick font: <output id="font-size-value"></output></label><input id="font-size" type="range" min="6" max="18" step="0.5"></div>
      <div class="control"><label for="axis-label-size">Axis-title font: <output id="axis-label-size-value"></output></label><input id="axis-label-size" type="range" min="6" max="18" step="0.5"></div>
      <div class="control"><label for="title-size">Figure-title font: <output id="title-size-value"></output></label><input id="title-size" type="range" min="6" max="18" step="0.5"></div>
      <div class="control"><label for="legend-size">Legend font: <output id="legend-size-value"></output></label><input id="legend-size" type="range" min="6" max="18" step="0.5"></div>
      <div class="control"><label for="hover-title-size">Hover title: <output id="hover-title-size-value"></output></label><input id="hover-title-size" type="range" min="6" max="12" step="0.5"></div>
      <div class="control"><label for="hover-value-size">Hover value: <output id="hover-value-size-value"></output></label><input id="hover-value-size" type="range" min="6" max="12" step="0.5"></div>
      <div class="control"><label for="major-ticks">Major-tick target: <output id="major-ticks-value"></output></label><input id="major-ticks" type="range" min="4" max="8" step="1"></div>
      <div class="control"><label for="x-axis-title-gap">X title gap: <output id="x-axis-title-gap-value"></output></label><input id="x-axis-title-gap" type="range" min="0.1" max="1" step="0.1"></div>
      <div class="control"><label for="y-axis-title-gap">Y title gap: <output id="y-axis-title-gap-value"></output></label><input id="y-axis-title-gap" type="range" min="0.1" max="1" step="0.1"></div>
      <div class="control"><label for="raw-width">Raw line: <output id="raw-width-value"></output></label><input id="raw-width" type="range" min="0.5" max="3" step="0.1"></div>
      <div class="control"><label for="fit-width">Fit line: <output id="fit-width-value"></output></label><input id="fit-width" type="range" min="0.5" max="3" step="0.1"></div>
      <div class="control"><label for="axis-width">Axis line: <output id="axis-width-value"></output></label><input id="axis-width" type="range" min="0.4" max="2" step="0.1"></div>
      <div class="control"><label for="marker-size">Marker diameter: <output id="marker-size-value"></output></label><input id="marker-size" type="range" min="2" max="9" step="0.5"></div>
      <div class="control"><label for="screen-width">Screen width: <output id="screen-width-value"></output></label><input id="screen-width" type="range" min="420" max="1200" step="10"></div>
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
const deliveryProfile = Object.freeze(__PROFILE__);
const FIXED_PROFILE_ID = "__PROFILE_ID__";
const STORAGE_KEY = `scientific-plotting:editable-resonance:${FIXED_PROFILE_ID}:v2`;
const layoutRoles = Object.freeze({
  title: {label: "Figure title", textKey: "title", fontKey: "titlePt"},
  xLabel: {label: "X-axis title", textKey: "xLabel", fontKey: "axisLabelPt"},
  yLabel: {label: "Y-axis title", textKey: "yLabel", fontKey: "axisLabelPt"},
  legend: {label: "Legend", textKey: null, fontKey: "legendPt"},
});
function freshLayoutOffsets() {
  return Object.fromEntries(Object.keys(layoutRoles).map(role => [role, {x: 0, y: 0}]));
}
function freshLayoutFontOverrides() {
  return Object.fromEntries(Object.keys(layoutRoles).map(role => [role, null]));
}
function profileState() {
  const profile = deliveryProfile;
  return {
    profileId: FIXED_PROFILE_ID,
    exportWidthMm: profile.exportWidthMm,
    exportHeightMm: profile.exportHeightMm,
    screenWidth: profile.screenWidthPx,
    fontPt: profile.tickPt,
    axisLabelPt: profile.axisLabelPt,
    titlePt: profile.figureTitlePt,
    legendPt: profile.legendPt,
    hoverTitlePt: profile.hoverTitlePt,
    hoverValuePt: profile.hoverValuePt,
    axisTitleGapEmX: profile.axisTitleGapEmX,
    axisTitleGapEmY: profile.axisTitleGapEmY,
    majorTickTarget: profile.majorTickTarget,
    rawWidthPt: profile.rawWidthPt,
    fitWidthPt: profile.fitWidthPt,
    axisWidthPt: profile.axisWidthPt,
    markerPt: profile.markerPt,
  };
}
const initialState = Object.freeze({
  ...profileState(),
  title: "Synthetic resonance response",
  xLabel: "Frequency (kHz)",
  yLabel: "Normalized response",
  rawLegend: "Raw data",
  fitLegend: "Fit guide",
  fontFamily: 'Calibri, "Microsoft YaHei", sans-serif',
  rawColor: "#2468a2",
  fitColor: "#c03a3a",
  xMin: 0,
  xMax: 100,
  yMin: 0,
  yMax: 1.2,
  interactionMode: "zoom",
  uiMode: "inspect",
  layoutOffsets: freshLayoutOffsets(),
  layoutFontOverrides: freshLayoutFontOverrides()
});
function cloneState(source) {
  return {
    ...source,
    layoutOffsets: Object.fromEntries(Object.entries(source.layoutOffsets || freshLayoutOffsets()).map(([role, offset]) => [role, {...offset}])),
    layoutFontOverrides: {...freshLayoutFontOverrides(), ...(source.layoutFontOverrides || {})},
  };
}
let state = cloneState(initialState);
let hoverIndex = null;
let selectedLayoutRole = null;
let layoutDrag = null;
const history = [];
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

function persistState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cloneState(state)));
}

function updateUndoButton() {
  document.getElementById("undo-edit").disabled = history.length === 0;
}

function snapshotState() {
  history.push(JSON.stringify(cloneState(state)));
  if (history.length > 30) history.shift();
  updateUndoButton();
}

function clearLayoutSelection() {
  Object.keys(layoutRoles).forEach(role => layoutElement(role)?.classList.remove("layout-selected"));
  selectedLayoutRole = null;
  document.getElementById("layout-inspector").hidden = true;
}

function layoutElement(role) {
  return {title: "plot-title", xLabel: "x-label", yLabel: "y-label", legend: "legend"}[role]
    ? document.getElementById({title: "plot-title", xLabel: "x-label", yLabel: "y-label", legend: "legend"}[role])
    : null;
}

function syncLayoutInspector() {
  const inspector = document.getElementById("layout-inspector");
  if (!selectedLayoutRole) {
    inspector.hidden = true;
    return;
  }
  const definition = layoutRoles[selectedLayoutRole];
  const offset = state.layoutOffsets[selectedLayoutRole];
  inspector.hidden = false;
  setText("selected-layout-name", `${definition.label} — presentation element`);
  const hasText = Boolean(definition.textKey);
  document.getElementById("layout-text-row").hidden = !hasText;
  document.getElementById("layout-text").value = hasText ? state[definition.textKey] : "";
  document.getElementById("layout-font-row").hidden = false;
  document.getElementById("layout-font-size").value = state.layoutFontOverrides[selectedLayoutRole] ?? state[definition.fontKey];
  document.getElementById("layout-offset-x").value = Number(offset.x.toFixed(2));
  document.getElementById("layout-offset-y").value = Number(offset.y.toFixed(2));
}

function selectLayoutRole(role) {
  if (!layoutRoles[role]) return;
  clearLayoutSelection();
  selectedLayoutRole = role;
  document.querySelector?.(".workspace")?.classList.remove("editor-collapsed");
  document.getElementById("toggle-editor-panel").setAttribute("aria-pressed", "true");
  setText("toggle-editor-panel", "Hide editor");
  layoutElement(role)?.classList.add("layout-selected");
  syncLayoutInspector();
  setText("status", `${layoutRoles[role].label} selected. Drag it or edit its properties.`);
}

function setUiMode(mode) {
  if (mode !== "inspect" && mode !== "layout") return;
  state.uiMode = mode;
  hoverIndex = null;
  if (mode !== "layout") clearLayoutSelection();
  render();
}

function applySelectedLayoutEdit() {
  if (!selectedLayoutRole) {
    setText("status", "Select a title, axis title, or legend first.");
    return;
  }
  snapshotState();
  const definition = layoutRoles[selectedLayoutRole];
  if (definition.textKey) state[definition.textKey] = document.getElementById("layout-text").value;
  state.layoutFontOverrides[selectedLayoutRole] = Number(document.getElementById("layout-font-size").value);
  state.layoutOffsets[selectedLayoutRole] = {
    x: Number(document.getElementById("layout-offset-x").value),
    y: Number(document.getElementById("layout-offset-y").value),
  };
  persistState();
  render();
  selectLayoutRole(selectedLayoutRole);
  setText("status", "Layout edit applied and saved in this browser.");
}

function niceTicks(minimum, maximum, targetCount = 6) {
  const span = maximum - minimum;
  if (!(span > 0) || !Number.isFinite(span)) return [minimum];
  const target = Math.max(2, Math.round(targetCount));
  const rawStep = span / (target - 1);
  const baseExponent = Math.floor(Math.log10(rawStep));
  const factors = [1, 2, 2.5, 5, 10];
  let best = null;
  for (let exponent = baseExponent - 1; exponent <= baseExponent + 1; exponent += 1) {
    for (const factor of factors) {
      const step = factor * 10 ** exponent;
      const epsilon = step * 1e-9;
      const start = Math.ceil((minimum - epsilon) / step) * step;
      const end = Math.floor((maximum + epsilon) / step) * step;
      const count = Math.max(0, Math.floor((end - start) / step + 1 + 1e-9));
      if (count < 2) continue;
      const preferredPenalty = count < 5 ? (5 - count) * 10 : count > 6 ? (count - 6) * 10 : 0;
      const stepPenalty = Math.abs(Math.log(step / rawStep));
      const score = preferredPenalty + stepPenalty;
      if (!best || score < best.score) best = {score, start, step, count};
    }
  }
  if (!best) return [minimum, maximum];
  return Array.from({length: best.count}, (_, index) => {
    const value = best.start + index * best.step;
    return Math.abs(value) < best.step * 1e-10 ? 0 : Number(value.toPrecision(12));
  });
}

function formatTick(value, step) {
  let decimals = 0;
  while (decimals < 6 && Math.abs(step * 10 ** decimals - Math.round(step * 10 ** decimals)) > 1e-8) decimals += 1;
  return value.toFixed(decimals);
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
  const box = svgEl("rect", {x: plot.left, y: plot.top, width: plot.right - plot.left, height: plot.bottom - plot.top, fill: "none", stroke: "#111", "stroke-width": axisStroke, class: "scientific-locked", "data-label": "Axis frame (locked)"});
  axes.appendChild(box);
  const xSpan = state.xMax - state.xMin;
  const ySpan = state.yMax - state.yMin;
  const xTicks = niceTicks(state.xMin, state.xMax, state.majorTickTarget);
  const yTicks = niceTicks(state.yMin, state.yMax, state.majorTickTarget);
  const xStep = xTicks.length > 1 ? xTicks[1] - xTicks[0] : xSpan;
  const yStep = yTicks.length > 1 ? yTicks[1] - yTicks[0] : ySpan;
  for (const x of xTicks) {
    const px = sx(x);
    axes.appendChild(svgEl("line", {x1: px, y1: plot.bottom, x2: px, y2: plot.bottom + 4, stroke: "#111", "stroke-width": axisStroke, class: "scientific-locked", "data-label": "X tick (locked)"}));
    const label = svgEl("text", {x: px, y: plot.bottom + 13, "text-anchor": "middle", fill: "#000", "data-axis": "x", "data-value": x, class: "x-tick-label scientific-locked", "data-label": "X tick label (locked)"});
    label.textContent = formatTick(x, xStep);
    axes.appendChild(label);
  }
  for (const y of yTicks) {
    const py = sy(y);
    axes.appendChild(svgEl("line", {x1: plot.left - 4, y1: py, x2: plot.left, y2: py, stroke: "#111", "stroke-width": axisStroke, class: "scientific-locked", "data-label": "Y tick (locked)"}));
    const label = svgEl("text", {x: plot.left - 7, y: py + 3, "text-anchor": "end", fill: "#000", "data-axis": "y", "data-value": y, class: "scientific-locked", "data-label": "Y tick label (locked)"});
    label.textContent = formatTick(y, yStep);
    axes.appendChild(label);
  }
}

function layoutAxisTitles() {
  const tickPx = state.fontPt * PT_TO_UNIT;
  const xLabelPx = (state.layoutFontOverrides.xLabel ?? state.axisLabelPt) * PT_TO_UNIT;
  const yLabelPx = (state.layoutFontOverrides.yLabel ?? state.axisLabelPt) * PT_TO_UNIT;
  const xGap = state.axisTitleGapEmX * xLabelPx;
  const yGap = state.axisTitleGapEmY * yLabelPx;
  const xLabel = document.getElementById("x-label");
  const safeBox = element => {
    try {
      const box = element.getBBox?.();
      return box && [box.x, box.y, box.width, box.height].every(Number.isFinite) ? box : null;
    } catch (_error) {
      return null;
    }
  };
  const tickBoxes = Array.from(document.getElementById("axes").querySelectorAll(".x-tick-label"))
    .map(safeBox)
    .filter(Boolean);
  const currentLabelY = Number(xLabel.getAttribute("y")) || 0;
  const xLabelBox = safeBox(xLabel);
  const tickBottom = tickBoxes.length
    ? Math.max(...tickBoxes.map(box => box.y + box.height))
    : plot.bottom + 13 + 0.2 * tickPx;
  const labelBaselineFromTop = xLabelBox
    ? currentLabelY - xLabelBox.y
    : 0.8 * xLabelPx;
  const xLabelBaseline = tickBottom + xGap + labelBaselineFromTop;
  xLabel.setAttribute("x", (177 + state.layoutOffsets.xLabel.x).toFixed(2));
  xLabel.setAttribute("y", (xLabelBaseline + state.layoutOffsets.xLabel.y).toFixed(2));
  xLabel.setAttribute("data-gap-em", state.axisTitleGapEmX);
  xLabel.setAttribute("data-gap-method", tickBoxes.length && xLabelBox ? "bbox" : "estimated");

  const yTicks = niceTicks(state.yMin, state.yMax, state.majorTickTarget);
  const yStep = yTicks.length > 1 ? yTicks[1] - yTicks[0] : state.yMax - state.yMin;
  const widestYLabel = Math.max(...yTicks.map(value => formatTick(value, yStep).length));
  const estimatedTickWidth = widestYLabel * 0.55 * tickPx;
  const yLabelX = Math.max(7, plot.left - 7 - estimatedTickWidth - yGap - 0.5 * yLabelPx);
  const yLabel = document.getElementById("y-label");
  const movedYLabelX = yLabelX + state.layoutOffsets.yLabel.x;
  const movedYLabelY = 108 + state.layoutOffsets.yLabel.y;
  yLabel.setAttribute("x", movedYLabelX.toFixed(2));
  yLabel.setAttribute("y", movedYLabelY.toFixed(2));
  yLabel.setAttribute("transform", `rotate(-90 ${movedYLabelX.toFixed(2)} ${movedYLabelY.toFixed(2)})`);
  yLabel.setAttribute("data-gap-em", state.axisTitleGapEmY);
}

function drawMarkers() {
  const markers = document.getElementById("markers");
  markers.replaceChildren();
  const radius = state.markerPt * PT_TO_UNIT / 2;
  data.raw.filter((_, i) => i % 10 === 0).forEach(d => {
    markers.appendChild(svgEl("circle", {cx: sx(d.x), cy: sy(d.y), r: radius, fill: "white", stroke: state.rawColor, "stroke-width": 0.8 * PT_TO_UNIT, class: "scientific-locked", "data-label": "Measured marker (locked)"}));
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
  const series = document.getElementById("hover-tooltip-series");
  const value = document.getElementById("hover-tooltip-value");
  value.textContent = `x ${point.x.toFixed(3)}; y ${point.y.toFixed(6)}`;
  const titlePx = state.hoverTitlePt * PT_TO_UNIT;
  const valuePx = state.hoverValuePt * PT_TO_UNIT;
  const tooltipWidth = Math.min(150, Math.max(78, 12 + Math.max(8 * titlePx * 0.62, value.textContent.length * valuePx * 0.55)));
  const tooltipHeight = 9 + titlePx + valuePx;
  const tooltipX = px > (plot.left + plot.right) / 2 ? px - tooltipWidth - 7 : px + 7;
  const tooltipY = Math.max(plot.top + 2, Math.min(py - tooltipHeight - 4, plot.bottom - tooltipHeight - 2));
  const box = document.getElementById("hover-tooltip-box");
  box.setAttribute("x", tooltipX); box.setAttribute("y", tooltipY);
  box.setAttribute("width", tooltipWidth.toFixed(2)); box.setAttribute("height", tooltipHeight.toFixed(2));
  series.setAttribute("x", tooltipX + 6); series.setAttribute("y", tooltipY + titlePx);
  value.setAttribute("x", tooltipX + 6); value.setAttribute("y", tooltipY + titlePx + valuePx + 3);
  crosshair.setAttribute("visibility", "visible");
  tooltip.setAttribute("visibility", "visible");
  setText("hover-readout", `Raw data — Frequency: ${point.x.toFixed(3)} kHz; response: ${point.y.toFixed(6)}`);
}

function renderInteractionMode() {
  const isLayout = state.uiMode === "layout";
  const isZoom = state.interactionMode === "zoom";
  document.getElementById("layout-edit-mode").setAttribute("aria-pressed", String(isLayout));
  document.getElementById("box-zoom-mode").setAttribute("aria-pressed", String(!isLayout && isZoom));
  document.getElementById("pan-mode").setAttribute("aria-pressed", String(!isLayout && !isZoom));
  for (const id of ["box-zoom-mode", "pan-mode", "zoom-in", "zoom-out", "reset-view"]) {
    document.getElementById(id).disabled = isLayout;
  }
  document.getElementById("chart").classList.toggle("edit-layout", isLayout);
  document.getElementById("interaction-surface").classList.toggle("pan-mode", !isZoom);
  setText("gesture-hint", isLayout
    ? "Layout edit: click or drag the title, axis titles, or legend. Scientific curves, points, axes, and ticks are locked."
    : isZoom
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
  setText("legend-raw", state.rawLegend);
  setText("legend-fit", state.fitLegend);
  const titleOffset = state.layoutOffsets.title;
  document.getElementById("plot-title").setAttribute("x", (177 + titleOffset.x).toFixed(2));
  document.getElementById("plot-title").setAttribute("y", (17 + titleOffset.y).toFixed(2));
  document.getElementById("plot-title").style.fontSize = `${(state.layoutFontOverrides.title ?? state.titlePt) * PT_TO_UNIT}px`;
  document.getElementById("plot-title").style.fontWeight = "700";
  for (const [id, role] of [["x-label", "xLabel"], ["y-label", "yLabel"]]) {
    document.getElementById(id).style.fontSize = `${(state.layoutFontOverrides[role] ?? state.axisLabelPt) * PT_TO_UNIT}px`;
    document.getElementById(id).style.fontWeight = "700";
  }
  for (const id of ["legend-raw", "legend-fit"]) {
    document.getElementById(id).style.fontSize = `${(state.layoutFontOverrides.legend ?? state.legendPt) * PT_TO_UNIT}px`;
  }
  document.getElementById("hover-tooltip-series").style.fontSize = `${state.hoverTitlePt * PT_TO_UNIT}px`;
  document.getElementById("hover-tooltip-value").style.fontSize = `${state.hoverValuePt * PT_TO_UNIT}px`;
  layoutAxisTitles();
  const legendOffset = state.layoutOffsets.legend;
  document.getElementById("legend").setAttribute("transform", `translate(${(224 + legendOffset.x).toFixed(2)} ${(31 + legendOffset.y).toFixed(2)})`);
  for (const id of ["legend-raw-line", "legend-fit-line"]) {
    document.getElementById(id).setAttribute("stroke", id.includes("raw") ? state.rawColor : state.fitColor);
    document.getElementById(id).setAttribute("stroke-width", (id.includes("raw") ? state.rawWidthPt : state.fitWidthPt) * PT_TO_UNIT);
  }
  Object.keys(layoutRoles).forEach(role => layoutElement(role)?.classList.toggle("layout-selected", role === selectedLayoutRole));
  syncLayoutInspector();
  syncControls();
}

function bindRange(id, key, suffix) {
  const input = document.getElementById(id);
  input.addEventListener("input", () => { state[key] = Number(input.value); render(); });
  input.addEventListener("change", persistState);
  return () => { input.value = state[key]; setText(`${id}-value`, `${state[key]}${suffix}`); };
}
const syncers = [
  bindRange("font-size", "fontPt", " pt"),
  bindRange("axis-label-size", "axisLabelPt", " pt"),
  bindRange("title-size", "titlePt", " pt"),
  bindRange("legend-size", "legendPt", " pt"),
  bindRange("hover-title-size", "hoverTitlePt", " pt"),
  bindRange("hover-value-size", "hoverValuePt", " pt"),
  bindRange("major-ticks", "majorTickTarget", ""),
  bindRange("x-axis-title-gap", "axisTitleGapEmX", " em"),
  bindRange("y-axis-title-gap", "axisTitleGapEmY", " em"),
  bindRange("raw-width", "rawWidthPt", " pt"),
  bindRange("fit-width", "fitWidthPt", " pt"),
  bindRange("axis-width", "axisWidthPt", " pt"),
  bindRange("marker-size", "markerPt", " pt"),
  bindRange("screen-width", "screenWidth", " px")
];
function bindText(id, key) {
  const input = document.getElementById(id);
  input.addEventListener("input", e => { state[key] = e.target.value; render(); });
  input.addEventListener("change", persistState);
}
bindText("title-input", "title");
bindText("x-label-input", "xLabel");
bindText("y-label-input", "yLabel");
bindText("raw-legend-input", "rawLegend");
bindText("fit-legend-input", "fitLegend");
document.getElementById("font-family").addEventListener("change", e => { state.fontFamily = e.target.value; render(); persistState(); });
document.getElementById("raw-color").addEventListener("input", e => { state.rawColor = e.target.value; render(); });
document.getElementById("raw-color").addEventListener("change", persistState);

function syncControls() {
  document.getElementById("title-input").value = state.title;
  document.getElementById("x-label-input").value = state.xLabel;
  document.getElementById("y-label-input").value = state.yLabel;
  document.getElementById("raw-legend-input").value = state.rawLegend;
  document.getElementById("fit-legend-input").value = state.fitLegend;
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

const chartNode = document.getElementById("chart");
chartNode.addEventListener("pointerdown", event => {
  if (state.uiMode !== "layout") return;
  const editable = event.target.closest?.(".layout-editable");
  const locked = event.target.closest?.(".scientific-locked");
  if (!editable) {
    if (locked) setText("status", `${locked.dataset?.label || "Scientific element"} cannot be moved; edit its semantic state instead.`);
    return;
  }
  event.preventDefault();
  const role = editable.dataset.layoutRole;
  selectLayoutRole(role);
  snapshotState();
  const point = clientToSvg(event);
  layoutDrag = {role, startX: point.x, startY: point.y, startOffset: {...state.layoutOffsets[role]}, moved: false};
  editable.setPointerCapture?.(event.pointerId);
});
chartNode.addEventListener("pointermove", event => {
  if (!layoutDrag) return;
  event.preventDefault();
  const point = clientToSvg(event);
  const dx = point.x - layoutDrag.startX;
  const dy = point.y - layoutDrag.startY;
  if (Math.hypot(dx, dy) > 0.75) layoutDrag.moved = true;
  state.layoutOffsets[layoutDrag.role] = {x: layoutDrag.startOffset.x + dx, y: layoutDrag.startOffset.y + dy};
  render();
});
function finishLayoutDrag() {
  if (!layoutDrag) return;
  if (layoutDrag.moved) {
    persistState();
    setText("status", `${layoutRoles[layoutDrag.role].label} moved and saved in this browser.`);
  } else {
    history.pop();
    updateUndoButton();
  }
  layoutDrag = null;
}
chartNode.addEventListener("pointerup", finishLayoutDrag);
chartNode.addEventListener("pointercancel", finishLayoutDrag);
chartNode.addEventListener("keydown", event => {
  if (state.uiMode !== "layout" || !["Enter", " "].includes(event.key)) return;
  const editable = event.target.closest?.(".layout-editable");
  if (!editable) return;
  event.preventDefault();
  selectLayoutRole(editable.dataset.layoutRole);
});

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
document.getElementById("layout-edit-mode").addEventListener("click", () => {
  const nextMode = state.uiMode === "layout" ? "inspect" : "layout";
  setUiMode(nextMode);
  setText("status", nextMode === "layout"
    ? "Layout edit enabled. Click or drag a presentation element; scientific data are locked."
    : "Data inspection enabled.");
});
document.getElementById("toggle-editor-panel").addEventListener("click", () => {
  const workspace = document.querySelector?.(".workspace");
  if (!workspace) return;
  const collapsed = workspace.classList.toggle("editor-collapsed");
  document.getElementById("toggle-editor-panel").setAttribute("aria-pressed", String(!collapsed));
  setText("toggle-editor-panel", collapsed ? "Show editor" : "Hide editor");
});
document.getElementById("undo-edit").addEventListener("click", () => {
  if (!history.length) {
    setText("status", "No edit to undo.");
    return;
  }
  state = cloneState(JSON.parse(history.pop()));
  selectedLayoutRole = null;
  hoverIndex = null;
  persistState();
  updateUndoButton();
  render();
  setText("status", "Last edit undone.");
});
document.getElementById("apply-layout-edit").addEventListener("click", applySelectedLayoutEdit);
document.getElementById("zoom-in").addEventListener("click", () => zoomAt(0.82));
document.getElementById("zoom-out").addEventListener("click", () => zoomAt(1.22));
document.getElementById("reset-view").addEventListener("click", () => { clearHover(); resetView(); setText("status", "Full view restored."); });

function download(name, type, content) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.getElementById("reset").addEventListener("click", () => {
  snapshotState();
  state = cloneState(initialState);
  hoverIndex = null;
  selectedLayoutRole = null;
  localStorage.removeItem(STORAGE_KEY);
  render();
  setText("status", "Defaults restored; browser-saved edits cleared.");
});
document.getElementById("download-state").addEventListener("click", () => { download("figure-state.json", "application/json", JSON.stringify({profile: state.profileId, state, data}, null, 2)); setText("status", "State downloaded."); });
function sanitizeSvgExport(copy) {
  const transientIds = ["hover-crosshair", "hover-tooltip", "box-zoom-rect", "interaction-surface"];
  for (const id of transientIds) copy.querySelector?.(`#${id}`)?.setAttribute("visibility", "hidden");
  copy.querySelectorAll?.(".layout-selected").forEach(element => element.classList.remove("layout-selected"));
  copy.querySelectorAll?.(".layout-editable, .scientific-locked").forEach(element => {
    element.classList.remove("layout-editable", "scientific-locked");
    element.removeAttribute("data-layout-role");
    element.removeAttribute("data-label");
    element.removeAttribute("tabindex");
  });
  return copy;
}
document.getElementById("export-svg").addEventListener("click", () => {
  const copy = sanitizeSvgExport(document.getElementById("chart").cloneNode(true));
  copy.setAttribute("xmlns", NS);
  copy.setAttribute("width", `${state.exportWidthMm}mm`);
  copy.setAttribute("height", `${state.exportHeightMm}mm`);
  download("synthetic-resonance.svg", "image/svg+xml", new XMLSerializer().serializeToString(copy));
  setText("status", `${state.exportWidthMm} mm SVG exported.`);
});
window.__figureTest = {
  getState: () => ({...state}),
  setState: patch => {
    state = cloneState({...state, ...patch});
    state.profileId = initialState.profileId;
    state.exportWidthMm = initialState.exportWidthMm;
    state.exportHeightMm = initialState.exportHeightMm;
    render();
  },
  getSvg: () => document.getElementById("chart"),
  zoomAt,
  panBySvg,
  hoverNearestAt,
  clearHover,
  setInteractionMode,
  applyBoxZoom,
  niceTicks,
  getHoverIndex: () => hoverIndex,
  resetView,
  getProfile: () => JSON.parse(JSON.stringify(deliveryProfile)),
  setUiMode,
  selectLayoutRole,
  applySelectedLayoutEdit,
  getSelectedLayoutRole: () => selectedLayoutRole,
  getHistoryLength: () => history.length,
  sanitizeSvgExport,
  restoreSavedState,
};
function restoreSavedState() {
  try {
    const savedState = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (!savedState?.layoutOffsets) return false;
    state = cloneState({...initialState, ...savedState});
    state.profileId = initialState.profileId;
    state.exportWidthMm = initialState.exportWidthMm;
    state.exportHeightMm = initialState.exportHeightMm;
    state.uiMode = "inspect";
    selectedLayoutRole = null;
    hoverIndex = null;
    setText("status", "Browser-saved figure edits restored.");
    render();
    return true;
  } catch (_error) {
    localStorage.removeItem(STORAGE_KEY);
    setText("status", "Invalid browser-saved state ignored.");
    return false;
  }
}
if (!restoreSavedState()) render();
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


def nice_ticks(minimum: float, maximum: float, target_count: int = 6) -> list[float]:
    """Return 5-6 round linear ticks when the range permits it."""
    span = maximum - minimum
    if not span > 0:
        return [minimum]
    target = max(2, round(target_count))
    raw_step = span / (target - 1)
    base_exponent = math.floor(math.log10(raw_step))
    best: tuple[float, float, float, int] | None = None
    for exponent in range(base_exponent - 1, base_exponent + 2):
        for factor in (1.0, 2.0, 2.5, 5.0, 10.0):
            step = factor * 10**exponent
            epsilon = step * 1e-9
            start = math.ceil((minimum - epsilon) / step) * step
            end = math.floor((maximum + epsilon) / step) * step
            count = max(0, math.floor((end - start) / step + 1 + 1e-9))
            if count < 2:
                continue
            preferred_penalty = (5 - count) * 10 if count < 5 else (count - 6) * 10 if count > 6 else 0
            score = preferred_penalty + abs(math.log(step / raw_step))
            if best is None or score < best[0]:
                best = (score, start, step, count)
    if best is None:
        return [minimum, maximum]
    _, start, step, count = best
    return [0.0 if abs(start + index * step) < step * 1e-10 else start + index * step for index in range(count)]


def render_preview(
    data: dict[str, list[dict[str, float]]],
    output: Path,
    profile: dict[str, float | str],
    hover_index: int | None = None,
) -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": profile["tickPt"],
            "font.family": ["Calibri", "Microsoft YaHei"],
            "axes.titlesize": profile["figureTitlePt"],
            "axes.labelsize": profile["axisLabelPt"],
            "axes.titlecolor": "black",
            "axes.labelcolor": "black",
            "xtick.labelsize": profile["tickPt"],
            "ytick.labelsize": profile["tickPt"],
            "xtick.color": "black",
            "ytick.color": "black",
            "legend.fontsize": profile["legendPt"],
            "legend.labelcolor": "black",
            "text.color": "black",
            "lines.linewidth": profile["rawWidthPt"],
            "axes.grid": False,
            "savefig.dpi": 300,
        }
    )
    mm_to_in = lambda mm: mm / 25.4
    figure, axis = plt.subplots(
        figsize=(mm_to_in(float(profile["exportWidthMm"])), mm_to_in(float(profile["exportHeightMm"]))),
        constrained_layout=True,
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
        linewidth=profile["fitWidthPt"],
        linestyle="--",
        label="Fit guide",
    )
    selected = data["raw"][::10]
    axis.plot(
        [item["x"] for item in selected],
        [item["y"] for item in selected],
        linestyle="none",
        marker="o",
        markersize=profile["markerPt"],
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
    axis.xaxis.labelpad = float(profile["axisLabelPt"]) * float(profile["axisTitleGapEmX"])
    axis.yaxis.labelpad = float(profile["axisLabelPt"]) * float(profile["axisTitleGapEmY"])
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
            fontsize=profile["hoverValuePt"],
            color="black",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#217565", "alpha": 0.96},
        )
    figure.savefig(output)
    plt.close(figure)


def render_wide_preview(output: Path, profile: dict[str, float | str], show_hover: bool = False) -> None:
    """Render a deterministic 185 mm single-wide profile regression fixture."""
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": profile["tickPt"],
            "font.family": ["Calibri", "Microsoft YaHei"],
            "axes.titlesize": profile["figureTitlePt"],
            "axes.labelsize": profile["axisLabelPt"],
            "axes.titlecolor": "black",
            "axes.labelcolor": "black",
            "xtick.labelsize": profile["tickPt"],
            "ytick.labelsize": profile["tickPt"],
            "xtick.color": "black",
            "ytick.color": "black",
            "legend.fontsize": profile["legendPt"],
            "legend.labelcolor": "black",
            "text.color": "black",
            "lines.linewidth": profile["rawWidthPt"],
            "axes.grid": False,
            "savefig.dpi": 300,
        }
    )
    x_values = [float(value) for value in range(-640, 521)]
    centers = [-575, -490, -405, -315, -225, -140, -45, 55, 150, 245, 335, 430]
    y_values: list[float] = []
    for x_value in x_values:
        response = 1.01 + 0.012 * math.sin(x_value * 0.19) + 0.008 * math.sin(x_value * 0.73)
        for center in centers:
            response -= 0.42 * math.exp(-((x_value - center) / 3.2) ** 2)
        y_values.append(response)
    marker_values = [y_values[int(center + 640)] for center in centers]
    wide_ticks = nice_ticks(-640, 520, 6)
    wide_y_ticks = nice_ticks(0.5, 1.08, 6)
    if wide_ticks != [-500.0, -250.0, 0.0, 250.0, 500.0]:
        raise RuntimeError(f"Unexpected wide-profile ticks: {wide_ticks}")
    if not 5 <= len(wide_y_ticks) <= 6:
        raise RuntimeError(f"Unexpected wide-profile y ticks: {wide_y_ticks}")

    mm_to_in = lambda mm: mm / 25.4
    figure, axis = plt.subplots(
        figsize=(mm_to_in(float(profile["exportWidthMm"])), mm_to_in(float(profile["exportHeightMm"]))),
        constrained_layout=True,
    )
    axis.plot(x_values, y_values, color="#2468a2", alpha=0.72, label="Wide scan")
    axis.plot(
        centers,
        marker_values,
        linestyle="none",
        marker="o",
        markersize=profile["markerPt"],
        markerfacecolor="#218c5b",
        markeredgecolor="white",
        markeredgewidth=0.8,
        label="Detected resonance",
    )
    axis.set(
        xlabel="Relative frequency (GHz)",
        ylabel="Normalized transmission",
        xlim=(-640, 520),
        ylim=(0.5, 1.08),
    )
    axis.set_xticks(wide_ticks)
    axis.set_yticks(wide_y_ticks)
    axis.tick_params(direction="out", width=0.9)
    axis.xaxis.labelpad = float(profile["axisLabelPt"]) * float(profile["axisTitleGapEmX"])
    axis.yaxis.labelpad = float(profile["axisLabelPt"]) * float(profile["axisTitleGapEmY"])
    for spine in axis.spines.values():
        spine.set_linewidth(0.9)
    figure.suptitle(
        "Wide scan with detected resonances", fontsize=profile["figureTitlePt"]
    )
    axis.legend(
        frameon=True,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=2,
        borderaxespad=0,
    )
    if show_hover:
        from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker

        hover_index = 7
        point_x = centers[hover_index]
        point_y = marker_values[hover_index]
        axis.axvline(point_x, color="#217565", linewidth=1.05, linestyle=(0, (5, 4)))
        axis.axhline(point_y, color="#217565", linewidth=1.05, linestyle=(0, (5, 4)))
        tooltip = VPacker(
            children=[
                TextArea(
                    "Wide scan",
                    textprops={"fontsize": profile["hoverTitlePt"], "fontweight": "bold", "color": "black"},
                ),
                TextArea(
                    f"{point_x:.3f} GHz; {point_y:.6f}",
                    textprops={"fontsize": profile["hoverValuePt"], "color": "black"},
                ),
            ],
            align="left",
            pad=0,
            sep=2,
        )
        axis.add_artist(
            AnnotationBbox(
                tooltip,
                (point_x, point_y),
                xybox=(74, 30),
                xycoords="data",
                boxcoords="offset points",
                frameon=True,
                bboxprops={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#217565", "alpha": 0.96},
            )
        )
    figure.savefig(output)
    plt.close(figure)


def main() -> None:
    profiles = load_profiles()
    validate_profiles(profiles)
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=fixture_dir / "editable-resonance.html"
    )
    parser.add_argument(
        "--profile-id",
        choices=sorted(profiles),
        default="90mm-single",
        help="Physical delivery profile fixed into the generated HTML.",
    )
    parser.add_argument(
        "--preview-png", type=Path, default=fixture_dir / "profile-preview.png"
    )
    parser.add_argument(
        "--interaction-preview-png",
        type=Path,
        default=fixture_dir / "hover-preview.png",
    )
    parser.add_argument(
        "--wide-preview-png",
        type=Path,
        default=fixture_dir / "wide-profile-preview.png",
    )
    parser.add_argument(
        "--wide-hover-preview-png",
        type=Path,
        default=fixture_dir / "wide-hover-preview.png",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data = build_data()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    profile_payload = json.dumps(
        profiles[args.profile_id], ensure_ascii=False, separators=(",", ":")
    )
    output.write_text(
        HTML_TEMPLATE.replace("__DATA__", payload)
        .replace("__PROFILE__", profile_payload)
        .replace("__PROFILE_ID__", args.profile_id),
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    if args.preview_png:
        preview = args.preview_png.resolve()
        preview.parent.mkdir(parents=True, exist_ok=True)
        render_preview(data, preview, profiles["90mm-single"])
        print(preview)
    if args.interaction_preview_png:
        interaction_preview = args.interaction_preview_png.resolve()
        interaction_preview.parent.mkdir(parents=True, exist_ok=True)
        render_preview(data, interaction_preview, profiles["90mm-single"], hover_index=52)
        print(interaction_preview)
    if args.wide_preview_png:
        wide_preview = args.wide_preview_png.resolve()
        wide_preview.parent.mkdir(parents=True, exist_ok=True)
        render_wide_preview(wide_preview, profiles["185mm-wide"])
        print(wide_preview)
    if args.wide_hover_preview_png:
        wide_hover_preview = args.wide_hover_preview_png.resolve()
        wide_hover_preview.parent.mkdir(parents=True, exist_ok=True)
        render_wide_preview(wide_hover_preview, profiles["185mm-wide"], show_hover=True)
        print(wide_hover_preview)


if __name__ == "__main__":
    main()
