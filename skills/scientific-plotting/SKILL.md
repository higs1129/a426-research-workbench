---
name: scientific-plotting
description: Creates, regenerates, or revises traceable scientific figures and standard semantic SVG from authoritative data, qualified inline-data HTML, or grouped vector sources. Use when a scientific figure is an intended output or must be made structurally editable. Do not use for interpreting an unchanged figure, page-level poster layout, general image editing, or decorative illustration.
metadata:
  version: "2.3"
  skill-author: "Personal Research Workflow"
---

# Scientific Plotting

## Purpose and boundary

Create scientific figures that remain interpretable at their declared delivery size and whose data, axes, labels, legends, and annotations have stable semantic structure. This Skill owns scientific-figure generation and reconstruction. A parent poster or report owns page placement.

Do not treat an SVG extension as proof of recoverable data or semantics. Preserve provenance and distinguish exact regeneration from approximate canvas reconstruction.

## Fixed source route

For a new or revised scientific figure, use the first available route and do not skip ahead for convenience:

1. **Authoritative data and plotting code** — regenerate the figure exactly.
2. **Qualified self-contained inline-data HTML** — extract the embedded physical data, units, scales, series semantics, configuration, and provenance, then regenerate exactly.
3. **Grouped AI or independent structured SVG** — export all requested panels once, read the old axes, units, ticks, legends, annotations, object groups, and canvas geometry, build an explicit figure model, discard the old visual axes/text/tspan fragments, and redraw a standard semantic SVG. When only canvas coordinates are recoverable, mark the result as approximate reconstruction.
4. **Otherwise stop** — request a grouped AI source or an independent SVG. Do not substitute a screenshot, raster crop, white-mask cleanup, partial-label patch, or hand-guessed axis.

Grouped AI must expose explicit panel groups or artboards. Convert or open one source once and batch-export its panels; do not repeatedly start an external editor. Illustrator/COM is not a default route and may be used only after explicit user permission and one successful capability probe.

Read [references/source-and-svg-contract.md](references/source-and-svg-contract.md) whenever the source is inline-data HTML, AI, SVG, EPS, PDF, or a quantitative raster field.

## Standard output contract

Generate one standard semantic SVG for each independently interpretable scientific module. Use only these publication baselines unless the user or journal provides another explicit specification:

- `90mm-single`: 85–90 mm final width;
- `185mm-double`: 180–185 mm final width for a single wide plot;
- `185mm-composite`: 180–185 mm final width for a true multipanel composite.

The SVG must:

- use `data-role="scientific-figure"` on the root;
- declare physical `width`/`height` in millimetres and use the same numeric dimensions in `viewBox`, with `data-user-unit-mm="1"`; one SVG user unit then equals one millimetre at the declared delivery size;
- embed a JSON figure model in `<metadata data-role="figure-model">`;
- declare `data-source-origin` and `data-coordinate-confidence` as either exact or approximate;
- keep text live and use semantic `<tspan>` subscript/superscript when needed;
- separate data series, axes, x/y ticks, axis titles, legend, annotations, plot area, and raster field with stable ids, classes, and `data-role` values;
- centralize typography and stroke settings in CSS variables;
- retain each curve or point series as an independent path, polyline, or symbol group;
- keep a quantitative heatmap as an embedded raster field only when its axes, ticks, titles, colorbar, and annotations remain vector;
- use the font stack `Calibri, "Microsoft YaHei", sans-serif`;
- contain no scripts, event handlers, network dependencies, machine-local paths, legacy SVG fonts, whole-figure non-uniform scaling, or `non-scaling-stroke`.

The figure model is the production interface. It records axis domains and scales, ticks, series points or normalized reconstruction geometry, labels, units, legend and annotation semantics, profile, source origin, coordinate confidence, and any raster-field calibration. A vector reconstruction with only canvas coordinates must use:

```text
data-source-origin="canvas-reconstruction"
data-coordinate-confidence="approximate"
```

Data/code and qualified inline-data HTML use exact confidence. Never upgrade approximate geometry to an exact scientific claim.

Use [scripts/render_semantic_svg.py](scripts/render_semantic_svg.py) to render a figure model and [scripts/check_semantic_svg_integrity.py](scripts/check_semantic_svg_integrity.py) for cheap file-integrity checks. These helpers do not decide the scientific meaning of a panel.

For an interactive report figure, the selected adapter owns its semantic SVG as well as its live view. Read [references/report-component.md](references/report-component.md). The Matplotlib component exports the current rendered SVG with model and semantic roles; a second call to the standalone semantic renderer is unnecessary. Its export converts Matplotlib point coordinates to the calibrated millimetre root through a declared uniform unit conversion, preserving physical size and layout.

## Figure construction rules

- Each module completes its own task and normally owns complete axes, units, ticks, legend, colorbar, scale bar, and claim-bearing annotations.
- Group modules only when they genuinely share an axis, legend, colorbar, cross-panel annotation, or comparison geometry. Do not prescribe heatmap-plus-spectrum, time-trace-plus-histogram, or any other chart-type pairing.
- Use boxed axes for ordinary quantitative plots unless an explicit local style requires open axes.
- Keep titles, axis labels, ticks, and in-figure text black with normal or bold weight. Do not use gray or light-weight text to create hierarchy.
- Omit grid lines unless the user requests them.
- Aim for about 5–6 readable major ticks on linear axes using round intervals.
- For scatter and point-line series, use a default marker diameter equal to `0.5 ×` the axis tick-label font size. Treat this as a presentation default rather than a data property: preserve an explicit user or source override, keep the marker diameter independently editable, and store the edited value in semantic figure state.
- Place legends and annotations away from data-bearing peaks, dips, uncertainty, and thresholds.
- Distinguish raw data, processed data, fit/theory, smoothing, uncertainty, and guides visually and in metadata.
- Do not non-uniformly scale a whole figure. A calibrated heatmap raster field may map into its declared plot box; photographs and micrographs remain proportional.
- A font change requires layout reflow. Do not apply a blanket point-size increase without recomputing margins and positions.
- Treat the physical viewport and typography as independent inputs. Changing the target width/height regenerates the plot geometry in the new millimetre coordinate system; it must not silently shrink the intended physical type or stroke tokens to force a fit.

Read [assets/style-profiles.json](assets/style-profiles.json) for ordinary 90 mm and 185 mm typography/stroke defaults. User, journal, accessibility, or established local requirements override them.

## Editable HTML mode

When the user requests an editable HTML figure, read [references/editable-html.md](references/editable-html.md). Editable HTML is a separate delivery wrapper around an authoritative data/state model and SVG view; it is not a poster-specific profile.

For an ordinary single-linear-axes Matplotlib line, scatter, or spectrum, use [references/matplotlib-fast-path.md](references/matplotlib-fast-path.md) and [scripts/render_matplotlib_editable.py](scripts/render_matplotlib_editable.py). Use [references/renderer-contract.md](references/renderer-contract.md) only for genuinely custom or multi-axes interaction.

The model proposes scientific content, chart type, initial domains and placement. After confirmation, keep authoritative data, processing, complete presentation state and adapter identity together. Report reading, expanded inspection, saving and export consume that component. Explicit user edits update current state; opening a viewer changes the surrounding container only. Capability gaps require a concrete explanation and confirmation before switching the selected adapter or design.

## Completion and integrity language

Run only cheap checks by default: parseability, finite numbers, required model/roles, unique ids, resolved local references, retained text/data objects, and declared fallback fonts. Do not automatically generate browser screenshots, run aesthetic review loops, or declare scientific correctness, `PASS`, publication readiness, or print readiness.

At handoff report:

- source route and provenance;
- standard profile and output file;
- exact or approximate coordinate confidence;
- any missing source semantics or manual reconstruction;
- that file integrity was checked and scientific/visual approval remains with the user.

## Failure modes

- Cropping or masking a quantitative plot instead of using the fixed source route.
- Reading grouped AI/SVG curve geometry before first recovering axis, unit, tick, legend, and annotation semantics.
- Keeping old Illustrator axes and text while also drawing new ones.
- Treating canvas-space vector paths as exact physical data.
- Returning an SVG that only wraps a plot screenshot.
- Prescribing subplot combinations from chart types rather than scientific coupling.
- Applying non-uniform scaling to a whole figure or photograph.
- Converting live text to outlines or retaining legacy `<font>/<glyph>` tables.
- Mutating measured points, fitted coordinates, tick values, color mappings, or data-linked anchors during presentation edits.
- Declaring a figure scientifically correct because a parser or integrity checker succeeded.

## Resources

- [references/source-and-svg-contract.md](references/source-and-svg-contract.md): source hierarchy, figure-model schema, grouped-vector reconstruction, semantic SVG structure, and heatmap rules.
- [references/editable-html.md](references/editable-html.md): editable browser delivery and semantic state.
- [references/matplotlib-fast-path.md](references/matplotlib-fast-path.md): maintained standard Matplotlib-to-editable-HTML path.
- [references/renderer-contract.md](references/renderer-contract.md): custom interactive SVG adapter boundary.
- [assets/style-profiles.json](assets/style-profiles.json): standard physical figure profiles.
- [scripts/render_semantic_svg.py](scripts/render_semantic_svg.py): deterministic standard semantic SVG renderer from an explicit figure model.
- [scripts/check_semantic_svg_integrity.py](scripts/check_semantic_svg_integrity.py): cheap structural and dependency integrity check without a scientific verdict.
- [scripts/render_matplotlib_editable.py](scripts/render_matplotlib_editable.py): maintained editable Matplotlib renderer.
- [scripts/bundle_editable_figure.py](scripts/bundle_editable_figure.py): offline editable-HTML bundler.
- [references/report-component.md](references/report-component.md): report integration, portable state and targeted development regression.
- [scripts/bundle_report_figures.py](scripts/bundle_report_figures.py): embeds qualified components in a report shell without redrawing.
