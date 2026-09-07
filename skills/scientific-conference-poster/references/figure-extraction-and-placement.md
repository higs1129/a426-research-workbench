# Scientific figures in posters

Read this reference before replacing a wireframe figure placeholder.

## Evidence unit first

For each figure record its asset class, poster claim, target panel/object, required axes/units/legend/colorbar/scale bar/annotations, excluded neighboring content, and approved slot dimensions. Each figure completes its own task unless it genuinely shares an axis, legend, colorbar, annotation, or comparison geometry with another module.

Do not prescribe pairings from chart types. Independent plots may be placed next to one another in HTML with explicit gaps and no overlap.

## Quantitative source route

Quantitative figures follow the `scientific-plotting` source route:

1. authoritative data and plotting code;
2. qualified self-contained inline-data HTML;
3. grouped AI or independent structured SVG, reconstructed into the standard figure model;
4. blocked until the user supplies grouped AI or independent SVG.

There is no screenshot, composite-raster crop, white-mask, old-axis patch, or partial panel fallback.

Use [inspect_figure_sources.py](../scripts/inspect_figure_sources.py) for mechanical source clues. For a source with named panels, convert/open it once and use [extract_grouped_panels.py](../scripts/extract_grouped_panels.py) with one manifest to export all panels. Intermediate files stay temporary unless the user requests reusable SVG sidecars.

Grouped vector reconstruction must first recover axis titles, units, scales, ticks, series identities, legends, annotations, and panel boundaries. Only then may it discard old Illustrator axes/text and redraw the standard semantic SVG. Canvas-derived coordinates remain marked approximate.

## Standard semantic SVG handoff

The accepted quantitative input is an inline SVG whose root has:

- `data-role="scientific-figure"`;
- `data-source-origin`;
- `data-coordinate-confidence`;
- standard profile identity;
- embedded `<metadata data-role="figure-model">`;
- stable semantic groups for plot area, data series, axes, ticks, titles, legend, and annotations.

The poster owns slot adaptation. Use [adapt_semantic_svg_for_slot.py](../scripts/adapt_semantic_svg_for_slot.py) to change outer physical width/height, plot-box aspect, margins, font/stroke/tick tokens, legend/annotation placement, and subplot gaps. The adapter recalculates semantic geometry; it does not apply `scaleX/scaleY` to the whole figure or change source confidence.

## Millimetre-calibrated slot contract

Freeze two independent inputs for every quantitative slot:

- slot capacity: final physical width and height in millimetres;
- poster typography baseline `B` in millimetres.

The adapted root uses the slot numbers directly:

```xml
<svg width="245mm" height="116mm"
     viewBox="0 0 245 116"
     data-user-unit-mm="1"
     data-poster-base-mm="10">
```

Thus one user unit equals one millimetre at the final size. Default poster tokens are `axis title = 0.95B`, `tick/annotation = 0.82B`, `data line = 0.07B`, `axis line = 0.06B`, and `tick length = 0.45B`; explicit approved overrides remain available. CSS variables express these current user units with `px` because CSS requires a length, while geometry attributes use unitless values.

Changing the box triggers semantic reflow from the embedded figure model. Changing `B` triggers font, margin, tick, legend, annotation, and collision-sensitive position reflow. Never shrink `B` merely because the content does not fit; simplify the module or return to the wireframe. Do not use `non-scaling-stroke` because physical stroke widths must remain tied to the calibrated coordinate system.

If the slot cannot support readable content after semantic reflow, return to the wireframe.

## Non-data visual assets

For photographs, micrographs, device images, and schematics without a figure model, prefer:

1. standalone original;
2. complete structurally extracted vector/object group;
3. a documented rectangular crop only for non-quantitative image evidence.

Preserve aspect ratio, scale bars, labels, orientation, and natural edges. A crop must retain the full intended object and exclude neighboring fragments. It must not repair missing scientific content with a mask.

## Poster placement

- Inline standard semantic SVG directly in the formal HTML; do not keep an external sidecar by default.
- Namespace ids when several figures share one page.
- Keep visible four-sided clearance from dividers and adjacent content.
- Use normal-flow Grid or Flex gaps to prevent module overlap.
- Keep photos and micrographs proportional.
- Preserve the standard SVG figure model so final manual DOM/CSS edits remain possible.

## Review boundary

The automated check is limited to file integrity. It may verify that the SVG/model/roles exist and local references resolve. It does not decide whether the correct panel was selected, whether the scientific claim is justified, whether the figure looks good, or whether it is printable.

At handoff disclose exact versus approximate reconstruction, any source that was blocked, and any manual workaround. Use `awaiting user review`; do not declare `PASS`.
