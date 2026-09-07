# Scientific source and semantic-SVG contract

Read this reference when a figure comes from inline-data HTML, AI, SVG, EPS, vector PDF, or contains a quantitative raster field.

## Fixed source route

Use the first available source:

1. authoritative data plus plotting code;
2. qualified self-contained inline-data HTML;
3. grouped AI or independent structured SVG;
4. stop and request grouped AI or independent SVG.

A qualified HTML source contains physical data, units, domains and scales, series semantics, stable series-to-SVG ids, renderer version, provenance, the SVG result, and no network or machine-local dependency.

AI, EPS, PDF, and ordinary SVG usually preserve canvas objects rather than physical data. They can support structural reconstruction, but canvas-derived geometry remains approximate. Do not use screenshots, raster crops, white masks, partial old-coordinate cleanup, or guessed labels as a quantitative route.

## Figure-model schema

Use a JSON object with this minimum structure:

```json
{
  "figureId": "bm-spectrum",
  "profile": "90mm-single",
  "heightMm": 62,
  "sourceOrigin": "authoritative-data",
  "coordinateConfidence": "exact",
  "x": {"domain": [0, 25], "scale": "linear", "title": "Frequency", "unit": "GHz"},
  "y": {"domain": [-120, -40], "scale": "linear", "title": "Power", "unit": "dBm"},
  "series": [
    {"id": "free-running", "kind": "polyline", "label": "Free-running", "points": [[0, -90], [25, -110]]}
  ],
  "annotations": []
}
```

Allowed standard profiles are `90mm-single`, `185mm-double`, and `185mm-composite`. The renderer fixes the width from the profile; `heightMm` remains explicit.

Use `sourceOrigin=authoritative-data|inline-data-html` with `coordinateConfidence=exact`. Use `sourceOrigin=canvas-reconstruction` with `coordinateConfidence=approximate`. For approximate reconstruction, points may use a normalized `0..1` domain only when the model clearly records that coordinate system and does not imply physical calibration.

Axes require explicit domains, scale type, title, and unit where the source uses a unit. Tick values may be supplied; otherwise the renderer may generate readable ticks. Series require a stable id, kind, label, and finite points. Standard kinds are `polyline`, `scatter`, and `point-line`; `point-line` renders independently editable markers plus a connecting polyline. Unless a source or user override supplies another value, scatter and point-line marker diameter is half the tick-label font size. Keep fit/theory/raw/processed distinctions in each series' semantic role or metadata.

Optional fields include legend placement, annotations with data anchors, panel label, title, and a raster field. A raster field records an embedded data URI, pixel dimensions, field kind, interpolation, and axis mapping.

## Grouped AI or SVG reconstruction

Before discarding old presentation objects, recover and record:

- target panel identity and boundary;
- x/y titles, units, domains, scales, ticks, and tick labels;
- series identities and curve/point geometry;
- legend semantics and style mapping;
- colorbar, scale bar, arrows, and claim-bearing annotations;
- shared-axis or shared-legend dependencies.

Export all requested panels from one converted source in one batch. Each source panel must be a named top-level group or artboard. Preserve the original source unchanged.

Then build the figure model. Discard the old visual axes, tick text, free-floating tspans, panel fragments, and inherited neighboring labels. Redraw the figure from the model so old and new coordinate systems cannot coexist. If a required semantic field cannot be recovered without guessing, stop and request a better source.

## Standard semantic SVG

The SVG root must carry:

```xml
<svg data-role="scientific-figure"
     data-source-origin="authoritative-data"
     data-coordinate-confidence="exact"
     data-user-unit-mm="1"
     data-physical-coordinate-system="mm-isomorphic"
     width="90mm" height="58mm"
     viewBox="0 0 90 58"
     preserveAspectRatio="xMidYMid meet">
```

The numeric `viewBox` width and height must equal the physical millimetre viewport. This defines `1 SVG user unit = 1 mm` at the declared delivery size and makes font, stroke, marker, tick, and margin values physically auditable. Geometry and presentation attributes use unitless user-coordinate numbers. CSS custom properties require a CSS length, so values such as `--tick-label-size:2.47px` are valid here: inside this calibrated SVG, one CSS `px` maps to one current SVG user unit, not independently to a 96-dpi print pixel. Do not use a nonzero unitless CSS `font-size`, and do not infer physical size from `px` without this root contract.

Embed the complete model in `<metadata data-role="figure-model">`. Use stable, figure-prefixed ids and the following roles where applicable:

- `plot-area`
- `plot-box`
- `data-series`
- `axes`
- `ticks-x`, `ticks-y`
- `axis-title-x`, `axis-title-y`
- `legend`
- `annotations`
- `raster-field`
- `colorbar`

Centralize styling in CSS variables including:

```css
--figure-font-family: Calibri, "Microsoft YaHei", sans-serif;
--axis-label-size: 2.82px;
--tick-label-size: 2.47px;
--annotation-size: 2.47px;
--data-line-width: 0.35px;
--marker-diameter: 1.23px;
--axis-line-width: 0.28px;
--tick-length: 1.5px;
```

Text remains live. Use semantic tspans for subscript and superscript. Paths, points, axes, labels, legends, and annotations remain independently addressable. Do not embed scripts, event handlers, external URLs, machine-local paths, legacy SVG fonts, or editor-only hit targets.

Do not use `vector-effect="non-scaling-stroke"`. It decouples a stroke from the calibrated user coordinate and defeats physical line-width control. A change in physical viewport dimensions must regenerate or semantically remap plot geometry, margins, labels, and legend placement; it must not scale the old root as one object.

## Quantitative raster fields

A heatmap may retain a raster data field inside the SVG when it comes from authoritative data or a declared approximate reconstruction. Keep axes, ticks, titles, colorbar, and annotations vector. The raster field must:

- use a data URI;
- declare source pixel width and height;
- declare continuous or categorical field kind;
- use bicubic/Lanczos for continuous fields or nearest for categorical fields;
- sit inside a plot-coordinate clip path;
- be the only element allowed to use `preserveAspectRatio="none"`.

Photographs, micrographs, and whole scientific figures remain proportional.

## Cheap integrity check

Use `scripts/check_semantic_svg_integrity.py`. It checks XML parsing, finite numbers, profile width, required roles/model, live text, series objects, unique ids, local references, external dependencies, fallback fonts, and raster-field structure. It does not check whether the chosen panel, values, scientific interpretation, aesthetics, or print result are correct.

Report `file integrity satisfied; awaiting user review`, never `PASS` or `print-ready`.

## Stop conditions

Stop and request a grouped AI or independent SVG when:

- no authoritative data/HTML route exists and panel boundaries are not explicit;
- required axis, unit, series, or legend semantics cannot be recovered;
- the source is only a raster composite or screenshot;
- the SVG is only a wrapper around a full plot image;
- reconstructing the figure would require guessing scientific content.
