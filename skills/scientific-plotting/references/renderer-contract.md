# Editable figure runtime contract

Read this reference only when the standard Matplotlib route in [matplotlib-fast-path.md](matplotlib-fast-path.md) cannot represent the requested figure and a lower-level custom SVG adapter is required.

## Division of responsibility

The shared runtime at `assets/editable-figure-runtime.js` owns reusable browser behavior. It does not decide scientific geometry.

The runtime owns:

- wheel and button zoom;
- left-drag box zoom;
- explicit two-axis pan mode;
- Reset view and interaction-mode state;
- transient hover dispatch;
- browser-local state-store and bounded-history helpers;
- rendered SVG axis-title placement from actual bounding boxes;
- removal of interaction/editor overlays from clean SVG exports.

The project adapter owns:

- authoritative data loading and transformation;
- scales, axes, ticks, units, and numeric formatting;
- curves, points, fits, uncertainty, feature markers, and annotations;
- nearest-point or nearest-feature hit testing;
- tooltip contents and drawing;
- semantic editor controls and layout-edit behavior;
- the project-specific HTML/SVG structure and final output path.

Prefer structured data and configuration for ordinary differences. Use runtime hooks only where the runtime must call project-specific scientific behavior.

## Required shell markers

The project HTML shell passed to `scripts/bundle_editable_figure.py` must contain each marker exactly once:

```html
<!-- SCIENTIFIC_FIGURE_PROFILE -->
<!-- SCIENTIFIC_FIGURE_DATA -->
<!-- SCIENTIFIC_FIGURE_RUNTIME -->
<!-- SCIENTIFIC_FIGURE_ADAPTER -->
```

The bundler replaces these markers with one selected profile, authoritative JSON data, the shared runtime, and the project adapter. The result is a self-contained offline HTML file.

The profile marker becomes `<script type="application/json" id="scientific-figure-profile">`; the data marker becomes `<script type="application/json" id="scientific-figure-data">`. Parse them rather than duplicating values in JavaScript:

```javascript
const profile = JSON.parse(
  document.getElementById("scientific-figure-profile").textContent
);
const data = JSON.parse(
  document.getElementById("scientific-figure-data").textContent
);
```

## Interaction DOM

The shell may choose its own visual design, but use these `data-*` attributes for controls handled by the runtime:

```html
<div id="figure-root" data-sf-root>
  <button data-sf-action="box-zoom" aria-pressed="true">Box zoom</button>
  <button data-sf-action="pan" aria-pressed="false">Pan</button>
  <button data-sf-action="zoom-in">Zoom +</button>
  <button data-sf-action="zoom-out">Zoom −</button>
  <button data-sf-action="reset-view">Reset view</button>

  <svg id="figure-svg" viewBox="0 0 1000 650">
    <g id="scientific-geometry"></g>
    <g id="inspection-overlay" class="sf-transient"></g>
    <rect id="zoom-brush" class="sf-transient" visibility="hidden"></rect>
    <rect id="interaction-surface" data-sf-interaction-surface></rect>
  </svg>
</div>
```

The project must size the interaction surface and brush in the same SVG coordinate system as `plotBounds`.

## Adapter entry point

The adapter initializes the project's semantic state and renderer, then creates the fixed interaction controller:

```javascript
const root = document.getElementById("figure-root");
const surface = document.getElementById("interaction-surface");
const brush = document.getElementById("zoom-brush");

const fullView = {xMin: 0, xMax: 100, yMin: 0, yMax: 1.2};
const plotBounds = {left: 90, right: 970, top: 60, bottom: 560};

const controller = ScientificFigureRuntime.createController({
  root,
  surface,
  brush,
  plotBounds,
  fullView,
  initialView: fullView,
  hooks: {
    viewChanged({view, reason}) {
      figureState.view = view;
      renderScientificGeometry(figureState, reason);
    },
    inspect({plot, data, view}) {
      return findNearestAuthoritativePoint({plot, data, view});
    },
    renderInspection(result, context) {
      drawTransientCrosshairAndTooltip(result, context);
    },
    clearInspection() {
      clearTransientInspection();
    },
    beforeViewChange({next}) {
      return next; // return false to reject, or return a corrected view
    },
    modeChanged({pointerMode, enabled}) {
      updateGestureHint(pointerMode, enabled);
    },
  },
});

controller.setView(fullView, "initial");
```

Required project hooks are `viewChanged`, `inspect`, `renderInspection`, and `clearInspection`. `beforeViewChange` and `modeChanged` are optional.

The hit-test result must refer back to authoritative source data or a clearly declared derived series. Do not let the interaction layer invent or rewrite measured coordinates.

The built-in transforms assume two linear axes. For logarithmic, categorical, broken, or otherwise nonlinear axes, provide a `transforms` object with the needed `plotToData`, `zoomView`, `panView`, and `boxView` functions. Keep those scale-specific transforms in the adapter; the runtime continues to own the pointer state machine.

## Layout editing

Layout editing remains semantic and project-specific because eligible elements vary by figure. Reuse these runtime helpers:

- call `controller.setEnabled(false)` on entry so zoom, pan, and inspection cannot conflict with layout dragging;
- call `controller.setEnabled(true)` when returning to inspection mode;
- use `ScientificFigureRuntime.createHistory(limit)` for bounded undo snapshots;
- use `ScientificFigureRuntime.createStateStore(key, version)` for browser-local persistence;
- keep scientific geometry locked and implement drag only for semantic presentation elements.

Do not register arbitrary SVG nodes as editable merely because they are text or paths. The adapter must declare semantic roles explicitly.

## Axis-title placement

After rendering tick labels and applying final fonts, position the horizontal title from actual SVG boxes:

```javascript
ScientificFigureRuntime.placeHorizontalAxisTitle({
  title: document.getElementById("x-axis-title"),
  tickLabels: document.querySelectorAll(".x-tick-label"),
  gapEm: profile.axisTitleGapEmX,
  fontSizePx: profile.axisLabelPt * 96 / 72,
});
```

Call this again after font-family, font-size, label, tick-format, zoom, or view-range changes. The function returns `false` when rendered boxes are unavailable; the adapter may use a temporary estimate and retry on the next animation frame.

## Clean export

Clone and sanitize the SVG before serializing it:

```javascript
const cleanSvg = ScientificFigureRuntime.sanitizeSvg(
  document.getElementById("figure-svg"),
  [".project-only-overlay"]
);
```

Mark hover guides, tooltips, brush rectangles, selection outlines, and other transient elements with `.sf-transient` or `data-sf-editor-only`. The clean export keeps scientific data and accepted semantic layout edits, but removes interaction hit targets and editor metadata.

## Bundling command

Use explicit project paths:

```powershell
python scripts/bundle_editable_figure.py `
  --shell path/to/figure-shell.html `
  --adapter path/to/figure-adapter.js `
  --data path/to/figure-data.json `
  --profile-id 185mm-wide `
  --output path/to/final-figure.html
```

The task shell, adapter, and data remain with the task. The shared runtime remains in the Skill source and is embedded during bundling, so the final HTML has no network or Skill-path dependency.

## Extension rule

Add a runtime hook only when at least two materially different figures need the same lifecycle extension. Keep one-off scientific drawing logic in the project adapter. A growing list of arbitrary hooks is evidence that the boundary is wrong; prefer a structured series, annotation, or editor schema before adding another callback.
