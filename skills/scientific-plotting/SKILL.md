---
name: scientific-plotting
description: Creates, updates, or regenerates traceable scientific figures for experiments, reports, talks, and browser-based records, including editable HTML figures. Use when a figure is an intended output or an existing figure must be revised. Do not use for interpreting an unchanged figure, general image editing, or decorative illustration.
metadata:
  version: "1.16"
  skill-author: "Personal Research Workflow"
---

# Scientific Plotting

## Purpose and boundaries

Every new figure should be readable at its declared final presentation size. Choose the delivery profile before choosing font, line, or marker sizes; those values have no stable visual meaning without a target size.

This skill applies to new plots only unless the user asks to revise old figures.

It governs visual construction and verification, not the scientific interpretation of unchanged figures. Preserve data provenance and do not let styling, smoothing, or annotation imply evidence the data do not contain.

## When to use

- Use for a new or revised scientific plot, multipanel figure, quicklook, report figure, slide figure, or `session.md` figure.
- Use when plotting choices affect raw/processed data distinction, units, uncertainty, readability, or visual emphasis.
- Do not use when the task is only to explain an existing figure, edit a photograph, create decorative artwork, or write prose without producing a figure.

## Reproducible workflow

1. Identify the scientific question, intended audience, output format, target display or print size, data source, units, and whether the figure is exploratory or final.
2. Inspect the authoritative data and distinguish raw values, transformations, fits, smoothing, uncertainty, and annotations.
3. Before writing plotting code, search once for an existing task-local generator. For an ordinary single-linear-axes line, scatter, spectrum, or similarly standard data plot requested as editable HTML, use the Matplotlib fast path in [references/matplotlib-fast-path.md](references/matplotlib-fast-path.md): task code loads the data and constructs the Matplotlib figure; the maintained renderer exports editable SVG, embeds it in HTML, and attaches the shared interaction bridge. Do not hand-author SVG coordinates for these standard plots. Use the lower-level custom SVG adapter only for multi-axes, nonlinear, diagram-like, or otherwise structurally complex visuals that the fast path cannot represent.
4. Classify the feature structure, then select exactly one delivery profile for the figure: 90 mm single-column plot, 180-185 mm double-column-width plot, 180-185 mm composite publication figure, presentation, embedded editable HTML, or standalone editable HTML. User, journal, or local requirements override these defaults. This is a generation-time structural decision, not an end-user style toggle.
5. Choose the smallest layout that communicates the comparison without covering data or shrinking text; split panels when necessary.
6. Generate the figure with explicit labels, units, visual hierarchy, and output path outside tracked repositories when the figure is a research artifact.
7. Load the selected profile from [assets/style-profiles.json](assets/style-profiles.json). Treat it as the authoritative source for physical size, typography, strokes, markers, tick target, and interaction-readout typography in both Matplotlib and HTML/SVG renderers; do not maintain parallel renderer-specific defaults. Bind the formal deliverable to that profile's physical export width and height.
8. For editable HTML, read [references/editable-html.md](references/editable-html.md). Read [references/matplotlib-fast-path.md](references/matplotlib-fast-path.md) for a standard plot, or [references/renderer-contract.md](references/renderer-contract.md) only for the custom SVG route. Preserve the figure data, semantic style state, and SVG-based rendered view. Do not show a 90/185 mm delivery-profile selector in a formal figure; changing the physical-width class requires regeneration from the source configuration.
9. Generate the requested PNG, SVG, PDF, or HTML once at its intended scale, then run cheap deterministic checks against the actual deliverable for required labels, profile identity, editable structure, bounds, and known spacing contracts. Correct a material failure reported by those checks. Do not open a browser or start a screenshot-driven visual iteration loop during ordinary production unless the user asks for visual validation, the deterministic checks report an unresolved layout risk, or the figure uses a new/custom renderer whose behavior cannot be established structurally.

Normal figure production does not authorize Skill regression tests, fixture regeneration, automated browser test passes, generic visual inspection, extra preview PNGs, or comparison renders of both delivery profiles. Run those only when the user explicitly requests testing, deterministic validation exposes an unresolved risk, or the task explicitly includes development of the reusable renderer itself. Do not let internal validation artifacts become a second deliverable.

## Evidence and visual validation

Treat readability as a hard gate for every report, weekly-summary, monthly-summary, and meeting figure. A figure is not finished until it can be read at its declared final print size, normal browser zoom, or final slide scale without local magnification.

- Do not shrink fonts to fit more traces, panels, captions, or legend text. Split into more panels, move legends outside the axes, or reduce the number of visible traces.
- Use Calibri for English and other Latin text and Microsoft YaHei (`Microsoft YaHei`, 微软雅黑) for Chinese text. In mixed-language strings, configure Calibri first and Microsoft YaHei as the Chinese glyph fallback; verify both fonts are available before final export.
- Use one language for figure titles, axis titles, and panel titles. Default to English only. Use Chinese only when the current user explicitly requests Chinese; do not duplicate the same title in both languages.
- Use black, bold axis labels and tick labels by default. Every in-figure title, including figure, axes, and panel titles, must be black rather than gray. Gray text is acceptable only for secondary captions or de-emphasized notes outside the main data area.
- Omit grid lines by default. Add them only when the current user explicitly requests them for a figure.
- Use boxed axes for standalone scientific plots: left, bottom, right, and top borders should be visible unless a local style guide requires otherwise.
- Use outward ticks when possible. Tick marks should be long enough to be visible on screenshots and projectors.
- Keep the clear gap from the end of a major tick mark to its numeric label compact. Start at about `0.28 em` of the tick-label font on both axes; change it only for an actual collision or unusual typography.
- Leave enough margins around all axes so the first and last tick labels are not clipped, especially at `0`, `1000`, and powers of ten.
- Measure the clear edge-to-edge gap between each axis title and the nearest tick-label bounding box after rendering. Start the horizontal-axis title at `0.3 em`; start the rotated vertical-axis title more compactly at `0.2 em`. In SVG/HTML, use the rendered `getBBox()` bounds of the tick labels and axis title; in Matplotlib, draw the canvas and use renderer bounding boxes. Position the title from those measured edges so fixed baseline offsets, reserved margins, descender allowances, and `labelpad` are not added on top of the requested gap. Adjust within about `0.15-0.5 em` only when the rendered result requires it. This is not the distance from the axis spine.
- Aim for about 5-6 visible major ticks per linear axis. Choose a nice interval from `1, 2, 2.5, 5, 10 × 10^n` so ranges in the tens or hundreds normally use multiples of 10, 50, 100, or another comparably round step. Keep the true axis range, but do not force irregular endpoints to become ticks.
- Put legends, run parameters, and bandwidth text where they do not cover peaks, dips, bandwidth windows, best-point markers, or important raw fluctuations.
- For a horizontal legend placed immediately above the axes, start with about `0.25 em` of clear edge-to-edge space between the legend bounding box and the top axis spine. This is a compact default, not a large reserved title band; move or wrap the legend when it collides.
- Preserve an explicitly configured fixed major-tick locator in task code. The fast path may replace Matplotlib's default automatic locator with the shared nice-tick policy, but it must not replace `MultipleLocator` or `FixedLocator`; serialize that fixed policy so interactive HTML redraws retain the same interval or values.
- Measure a top legend and figure title after the Matplotlib canvas draw. When their horizontal spans intersect and their text bounds collide, place the title above the legend with the profile's compact clear gap and reserve a small browser-metric safety band by reducing only the axes height when needed. Recheck that gap once from browser bounding boxes, but stop automatic correction after the user manually moves either element. Stop with an actionable layout error if the fixed canvas cannot contain the resolved stack; do not hide the collision through repeated blind regeneration.
- If a bandwidth label conflicts with data, place the label near the corresponding threshold line or directly below the shaded bandwidth region, not on top of the feature being discussed.
- Use one clear frequency axis convention within a figure group. For related noise, response, and NEP plots, stack panels vertically and share the same frequency axis whenever comparison across frequency matters.
- Preserve visual hierarchy for raw and processed curves:
  - raw data: plotted first, slightly thicker, semi-transparent;
  - smoothed or fitted guide: plotted on top, slightly thinner, high opacity;
  - exact numeric optima should still come from raw data unless the user explicitly asks otherwise.
- For dense comparison plots, avoid making all lines fully opaque. Use alpha, small multiples, or interactive selection so the trend remains visible.
- Before finishing ordinary production, validate the generated deliverable deterministically: confirm it opens/parses, carries the selected profile and required labels, retains the expected vector/editable structure, and satisfies any measurable bounds or spacing checks available to the renderer. Use browser or screenshot inspection only for an explicitly requested visual review, a reported or structurally detected layout uncertainty, or targeted validation of new/custom shared rendering behavior.

## Size and delivery profiles

Use physical units for publication and vector figures. In Matplotlib, font size, line width, and `markersize` are in points (`pt`); `scatter(s=...)` uses points squared. Reserve `px` for browser layout and CSS. Increasing a canvas while keeping point sizes fixed makes those elements occupy a smaller fraction of the figure; scaling an already-rendered vector scales all elements together.

### 90 mm publication panel

Use 90 mm as the default final width for one ordinary panel when no journal or user specification exists. A width of 85-90 mm is acceptable when matching an established layout.

Prefer this single-column profile when the plot communicates one principal feature or one simple relationship, regardless of how many samples were acquired. Representative cases include one mechanical-mode peak, one optical-mode transmission spectrum, and a scatter or line plot whose main purpose is the trend of one physical quantity against another.

- tick labels and legend: start at 7 pt; use 6-8 pt only after checking the final-size rendering;
- axis labels: start at 8 pt;
- panel label or compact title: start at 9 pt;
- main data line: start at 1.0 pt;
- secondary or guide line: start at 0.7-0.8 pt;
- important marker diameter: start at 4-5 pt.

These are profile defaults, not universal minima. Prefer reducing visible content or changing layout before reducing essential text below 6 pt.

### 180-185 mm composite publication figure

Use 180-185 mm for a multi-panel or two-column composite, not automatically for a single ordinary plot. Compose it from panels designed around the 85-90 mm visual scale, with deliberate gutters, aligned axes, and shared labels where useful. Do not create a 90 mm panel and stretch it to 185 mm without reviewing typography and density.

### 180-185 mm double-column-width plot

Use a single axes at 180-185 mm when multiple distinct features must remain separately readable across the horizontal range, such as a broad transmission scan containing many resolved peaks, a dense event sequence, or many feature-linked annotations that would collide at single-column width. The number of sampled points, multiple series, or a long numeric range alone is not sufficient: if the figure still communicates only one principal peak or one trend, keep it single-column.

Selecting this width must also select its typography and stroke profile. At the declared final 180-185 mm size, start with:

- tick labels and ordinary in-figure text: 12 pt;
- legend: 12 pt;
- axis labels: 12 pt;
- figure title: 10 pt;
- compact hover readout: 9 pt series title and 8 pt numeric value;
- main data line: 1.2 pt;
- secondary or guide line: 0.9-1.0 pt;
- important marker diameter: 6 pt.

These are final-size defaults, not CSS sizes before responsive scaling. The hover readout is interaction chrome, so it must use its own compact tokens rather than inherit the 12 pt plot typography. If content collides, reduce annotation density, reposition the legend, increase height, or split the figure rather than silently scaling the whole style.

### Presentation

Choose the actual on-slide size first and enlarge typography, strokes, and markers for the viewing distance. Preserve the same visual hierarchy and color roles as the publication profiles, but do not force 6-8 pt publication text onto a projected slide.

### Browser HTML

Treat physical width as an export/design baseline rather than a literal browser width. Display a 90 mm single panel responsively at about 640-760 CSS px on desktop; a 180-185 mm single-wide figure may use about 900-1100 CSS px when the page permits. Mobile width remains `100%`. When the figure must remain editable, use SVG/DOM and the semantic editing contract in [references/editable-html.md](references/editable-html.md); avoid raster-only, Canvas, or WebGL output unless density requires a documented fallback.

Keep responsive screen width separate from the physical delivery profile. The browser editor may change the CSS preview width, typography, strokes, markers, labels, and other presentation state, but a formal HTML figure must keep one immutable export width and height. Retain both 90 mm and 185 mm definitions in the shared configuration so the generator can choose either one for different figures; expose a runtime profile switch only in a dedicated, clearly labeled comparison/demo tool explicitly requested by the user, never in the formal deliverable.

For browser SVG and HTML, use the font stack `Calibri, "Microsoft YaHei", sans-serif`. Calibri supplies English glyphs and Microsoft YaHei supplies Chinese fallback glyphs. Keep all rendered figure titles explicitly black.

Editable HTML figures should support wheel or button zoom, left-drag box zoom as the default pointer mode, and an explicit Pan mode whose left-drag moves both axis ranges. Hovering should snap to the nearest raw data point and show a solid focus marker, dashed horizontal and vertical guides, and exact numeric values; clear this transient readout on pointer leave rather than creating persistent selections that require a Clear selection action. Preserve an obvious Reset view path. Panning moves the viewport only; never allow interaction to move a measured data point or silently change its value.

Treat the shared JavaScript runtime as interaction infrastructure, not as a universal scientific renderer. The project adapter remains responsible for data transformations, scales, ticks, traces, uncertainty, feature detection, and special annotations. Prefer structured configuration for ordinary variation and use runtime callbacks only at the documented lifecycle boundaries; do not confuse these in-figure callbacks with Codex lifecycle Hooks.

Keep hover tooltips compact and content-sized. Their series and value fonts are separate from figure, tick, axis-label, and legend fonts; for the 185 mm profile use 9 pt and 8 pt respectively, cap the tooltip width when practical, and position it away from the inspected point.

Separate data inspection from layout editing. Default to inspection mode. Provide a visible `Edit layout` action that switches to direct manipulation: clicking a presentation element selects it, opens a context-specific inspector, and permits direct dragging when position is a presentation choice. Eligible elements include figure and axis titles, legends, panel labels, non-data-anchored explanatory notes, and the x- and y-axis numeric tick-label groups. Treat each axis's numeric labels as one presentation group with shared horizontal and vertical offsets; do not expose per-tick dragging by default. Give grouped elements a whole-bounds hit target so whitespace inside a legend or label group remains selectable. A data-linked annotation may move its label box, but its authoritative anchor remains fixed.

Lock scientific geometry in layout-edit mode. Curves, measured markers, fit/theory coordinates, uncertainty geometry, axis scales, tick values, tick marks and their axis positions, and data-linked anchors must not be freely dragged. Moving a tick-label group changes only its rendered label offset, never the tick values or mark locations. Clicking locked geometry should explain that it is locked and direct the user to the corresponding semantic control or source data. Keep selection highlight, undo, default restoration, browser-local persistence, and clean SVG export discoverable. Remove selection and interaction overlays from export.

For raster exports, use enough resolution for the declared physical size, commonly 180-300 dpi for reports or slides. Prefer SVG/PDF when downstream tools preserve vectors. Keep colors distinguishable on a projector and in grayscale when possible.

## Labels And Legends

- Do not let legends, text boxes, or parameter labels cover important curves, peaks, dips, ticks, or annotations.
- If a legend or parameter description is long, place it outside the plotting axes, usually on the right or below the plot.
- Put detailed run parameters in the caption, side panel, or session text instead of inside the data area.
- Prefer concise labels in the figure and fuller explanations in `session.md`.

### Layout checks

Before saving a figure:

1. Check that axis labels and tick labels are not clipped.
2. Check that the legend does not overlap the plotted signal or key annotations.
3. Check that long labels wrap or move outside the axes.
4. Check that the figure still works at its declared final print, browser, or slide scale, not only when zoomed in.
5. If there are multiple stages or parameter groups, use color bands or separate panels with a clear external legend.

Also verify that:

- every plotted quantity has an authoritative source and correct unit;
- data, fits, theory, smoothing, and guides-to-the-eye are visually and verbally distinguishable;
- uncertainty is shown when supported and not fabricated for single acquisitions;
- exact numeric claims come from the declared source rather than a visually convenient smoothed curve;
- the final file opens correctly and remains legible at slide, report, or publication size.

## Failure modes

- Finishing from source code without generating the requested deliverable and running the cheap deterministic checks appropriate to its format.
- Shrinking fonts to accommodate too many curves, panels, parameters, or legend entries.
- Allowing legends, labels, or shaded regions to obscure peaks, dips, thresholds, markers, or raw fluctuations.
- Styling a smoothed or fitted trace so strongly that it appears to be the measurement, or extracting exact optima from the smoothed guide without disclosure.
- Mixing incompatible frequency axes, units, normalizations, or calibration assumptions in one visual comparison.
- Saving final research figures into a tracked code repository instead of the user-provided or project-defined data/output location.
- Applying the default style mechanically when a journal, accessibility requirement, grayscale output, or local figure system requires a different choice.
- Specifying point or pixel sizes without declaring the final figure width and display context.
- Treating an embedded raster, Canvas plot, or raw SVG DOM as a user-editable HTML figure without providing semantic editing controls and state.
- Falling back to a single CJK-capable font for all mixed-language text, which silently replaces the requested Calibri English typography.
- Adding grid lines as a generic plotting default or rendering any in-figure title in gray.
- Duplicating English and Chinese in one title without an explicit request, or defaulting a new figure to Chinese.
- Choosing width from sample count or numeric span without first deciding whether the plot contains one principal feature or several distinct features.
- Expanding a one-peak or one-trend plot to 180-185 mm when it remains readable as a single-column figure.
- Applying the obsolete 16/16/14 pt wide-figure typography instead of the shared 185 mm profile's 12 pt plot text and 10 pt figure title.
- Exposing 90 mm and 185 mm as a runtime selector in one formal HTML figure, allowing its physical delivery contract to change after generation.
- Producing major ticks by equal interpolation between arbitrary endpoints, such as `-640, -447, -253, -60, ...`, instead of choosing a readable nice interval.
- Treating the axis-title gap as an arbitrary margin rather than checking the rendered edge-to-edge distance from tick labels.
- Adding a nominal `0.3 em` gap after a separate fixed baseline or margin allowance, producing a much larger visible gap than the profile requests.
- Hiding box zoom and two-axis pan behind an unexplained drag gesture, or retaining a persistent point selection whose clearing action is not obvious.
- Implementing zoom or pan by scaling text and axes until they become unreadable, or allowing drag interaction to change measured coordinates.
- Duplicating profile constants separately in Matplotlib and HTML/JavaScript, allowing the two outputs to drift.
- Letting a hover tooltip inherit the main plot font and grow large enough to obscure the data.
- Combining inspection, pan, and direct editing in one unexplained drag gesture.
- Implementing direct editing by serializing arbitrary SVG mutations without semantic state, undo, default restoration, or clean export.
- Allowing layout-edit mode to drag measured points, curves, tick positions, fitted coordinates, or data-linked anchors away from their authoritative values.
- Rewriting an already available HTML/SVG interaction layer for each new dataset instead of supplying a thin data and semantic-configuration adapter.
- Running fixture generation, cross-profile previews, browser automation, or the Skill test suite during ordinary figure production when the user did not request testing.
- Copying or editing the shared interaction runtime inside each research task instead of keeping a thin task adapter and bundling the maintained runtime into the final HTML.
- Hand-calculating SVG paths, axes, and tick geometry for a standard single-axes line or scatter plot that the Matplotlib fast path already supports.

## Tool-specific defaults

### Matplotlib

For a 90 mm publication panel, start from settings like:

```python
import json
from pathlib import Path

profiles = json.loads(Path("assets/style-profiles.json").read_text(encoding="utf-8"))
profile = profiles["90mm-single"]
plt.rcParams.update({
    "font.family": ["Calibri", "Microsoft YaHei"],
    "font.size": profile["tickPt"],
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
    "svg.fonttype": "none",
    "lines.linewidth": profile["rawWidthPt"],
    "axes.grid": False,
    "figure.dpi": 150,
    "savefig.dpi": 300,
})

mm_to_in = lambda mm: mm / 25.4
fig, ax = plt.subplots(
    figsize=(mm_to_in(profile["exportWidthMm"]), mm_to_in(profile["exportHeightMm"])),
    constrained_layout=True,
)
ax.xaxis.labelpad = profile["axisLabelPt"] * profile["axisTitleGapEmX"]
ax.yaxis.labelpad = profile["axisLabelPt"] * profile["axisTitleGapEmY"]

from matplotlib.ticker import MaxNLocator
ax.xaxis.set_major_locator(MaxNLocator(
    nbins=5,
    steps=[1, 2, 2.5, 5, 10],
    min_n_ticks=5,
))
```

`labelpad` is only an initial value because Matplotlib's baseline and layout calculations can make the visible edge-to-edge gap differ from the requested value. After the first draw, measure it and correct the pad once:

```python
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
tick_boxes = [label.get_window_extent(renderer) for label in ax.get_xticklabels() if label.get_visible()]
label_box = ax.xaxis.label.get_window_extent(renderer)
if tick_boxes:
    current_gap_px = min(box.y0 for box in tick_boxes) - label_box.y1
    desired_gap_px = profile["axisTitleGapEmX"] * profile["axisLabelPt"] * fig.dpi / 72
    ax.xaxis.labelpad += (desired_gap_px - current_gap_px) * 72 / fig.dpi
    fig.canvas.draw()
```

Apply the analogous measured correction to a vertical title when necessary. Do not keep increasing figure margins to solve a title-gap error.

`nbins=5` requests roughly five intervals, usually producing about 5-6 visible ticks; inspect the actual result and adjust when labels collide. For example, an axis range of `-640` to `520` may keep those limits while showing `-500, -250, 0, 250, 500`, rather than using equal interpolation or forcing both endpoints as labels.

Do not use `bbox_inches="tight"` when an exact final physical canvas size is required; it can change the saved dimensions. Inspect the saved file dimensions instead. For presentation figures, define a separate profile from the actual on-slide size rather than scaling these publication values mechanically.

For long legends:

```python
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0)
```

If the external legend needs more room, enlarge the figure instead of shrinking fonts.

### Measurement figures

For scope traces, spectra, PID sweeps, and lock timelines:

- Clearly state what each channel means, not only `CH1` or `CH2`.
- Put key numeric settings outside the axes when they are long.
- If showing lock stages, mark stages with readable color bands and a legend outside the data area.
- When plotting an accepted data group for external `session.md`, save both the raw data path and the representative figure path under `$DAILY_NOTE_DATA_ROOT` or a user-provided external output directory. Do not save generated figures into tracked repo paths.

## Reusable HTML resources

- [assets/editable-figure-runtime.js](assets/editable-figure-runtime.js): fixed viewport interaction, transient inspection dispatch, persistence/history helpers, measured horizontal-title placement, and clean-export sanitization.
- [assets/matplotlib-svg-bridge.js](assets/matplotlib-svg-bridge.js): fixed browser bridge for standard single-axes Matplotlib SVG figures; it owns dynamic ticks, line/scatter redraw, hover readout, compact presentation controls, whole-bounds selection, and selectable/undoable layout offsets for titles, axis labels, legends, and collective x/y tick-label groups.
- [scripts/render_matplotlib_editable.py](scripts/render_matplotlib_editable.py): default standard-plot renderer; it loads a small task-local plotting hook, applies one profile, exports text-preserving SVG, produces standalone HTML, and optionally records stage timings.
- [scripts/bundle_editable_figure.py](scripts/bundle_editable_figure.py): deterministic offline bundler; it packages a task shell, task adapter, JSON data, one fixed profile, and the shared runtime without deciding scientific geometry.
- [references/matplotlib-fast-path.md](references/matplotlib-fast-path.md): standard-plot hook contract, command, supported scope, timing report, and fallback boundary.
- [references/renderer-contract.md](references/renderer-contract.md): lower-level custom-SVG ownership boundary, required shell markers, adapter callbacks, layout-edit integration, and export contract.
