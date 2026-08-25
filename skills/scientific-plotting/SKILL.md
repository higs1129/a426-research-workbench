---
name: scientific-plotting
description: Creates, updates, or regenerates traceable scientific figures for experiments, reports, talks, and browser-based records, including editable HTML figures. Use when a figure is an intended output or an existing figure must be revised. Do not use for interpreting an unchanged figure, general image editing, or decorative illustration.
metadata:
  version: "1.5"
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
3. Select a delivery profile: 90 mm publication panel, 180-185 mm composite publication figure, presentation, embedded editable HTML, or standalone editable HTML. User, journal, or local requirements override these defaults.
4. Choose the smallest layout that communicates the comparison without covering data or shrinking text; split panels when necessary.
5. Generate the figure with explicit labels, units, visual hierarchy, and output path outside tracked repositories when the figure is a research artifact.
6. For editable HTML, read [references/editable-html.md](references/editable-html.md) and preserve the figure data, semantic style state, and SVG-based rendered view.
7. Render the actual PNG, SVG, PDF, or HTML and inspect it at its intended scale.
8. Apply the validation gate below and revise until no material clipping, overlap, ambiguity, misleading emphasis, or broken editing control remains.

## Evidence and visual validation

Treat readability as a hard gate for every report, weekly-summary, monthly-summary, and meeting figure. A figure is not finished until it can be read at its declared final print size, normal browser zoom, or final slide scale without local magnification.

- Do not shrink fonts to fit more traces, panels, captions, or legend text. Split into more panels, move legends outside the axes, or reduce the number of visible traces.
- Use Calibri for English and other Latin text and Microsoft YaHei (`Microsoft YaHei`, 微软雅黑) for Chinese text. In mixed-language strings, configure Calibri first and Microsoft YaHei as the Chinese glyph fallback; verify both fonts are available before final export.
- Use one language for figure titles, axis titles, and panel titles. Default to English only. Use Chinese only when the current user explicitly requests Chinese; do not duplicate the same title in both languages.
- Use black, bold axis labels and tick labels by default. Every in-figure title, including figure, axes, and panel titles, must be black rather than gray. Gray text is acceptable only for secondary captions or de-emphasized notes outside the main data area.
- Omit grid lines by default. Add them only when the current user explicitly requests them for a figure.
- Use boxed axes for standalone scientific plots: left, bottom, right, and top borders should be visible unless a local style guide requires otherwise.
- Use outward ticks when possible. Tick marks should be long enough to be visible on screenshots and projectors.
- Leave enough margins around all axes so the first and last tick labels are not clipped, especially at `0`, `1000`, and powers of ten.
- Keep axis titles separated from tick labels, but not so far away that the axis looks detached. Adjust label padding and plot margins instead of moving tick labels off their ticks.
- Put legends, run parameters, and bandwidth text where they do not cover peaks, dips, bandwidth windows, best-point markers, or important raw fluctuations.
- If a bandwidth label conflicts with data, place the label near the corresponding threshold line or directly below the shaded bandwidth region, not on top of the feature being discussed.
- Use one clear frequency axis convention within a figure group. For related noise, response, and NEP plots, stack panels vertically and share the same frequency axis whenever comparison across frequency matters.
- Preserve visual hierarchy for raw and processed curves:
  - raw data: plotted first, slightly thicker, semi-transparent;
  - smoothed or fitted guide: plotted on top, slightly thinner, high opacity;
  - exact numeric optima should still come from raw data unless the user explicitly asks otherwise.
- For dense comparison plots, avoid making all lines fully opaque. Use alpha, small multiples, or interactive selection so the trend remains visible.
- Before finishing, do at least one rendered visual check when practical: open the HTML/PDF/PNG, or capture a screenshot, and check for clipped labels, unreadable ticks, overlap, and misleading visual emphasis.

## Size and delivery profiles

Use physical units for publication and vector figures. In Matplotlib, font size, line width, and `markersize` are in points (`pt`); `scatter(s=...)` uses points squared. Reserve `px` for browser layout and CSS. Increasing a canvas while keeping point sizes fixed makes those elements occupy a smaller fraction of the figure; scaling an already-rendered vector scales all elements together.

### 90 mm publication panel

Use 90 mm as the default final width for one ordinary panel when no journal or user specification exists. A width of 85-90 mm is acceptable when matching an established layout.

- tick labels and legend: start at 7 pt; use 6-8 pt only after checking the final-size rendering;
- axis labels: start at 8 pt;
- panel label or compact title: start at 9 pt;
- main data line: start at 1.0 pt;
- secondary or guide line: start at 0.7-0.8 pt;
- important marker diameter: start at 4-5 pt.

These are profile defaults, not universal minima. Prefer reducing visible content or changing layout before reducing essential text below 6 pt.

### 180-185 mm composite publication figure

Use 180-185 mm for a multi-panel or two-column composite, not automatically for a single ordinary plot. Compose it from panels designed around the 85-90 mm visual scale, with deliberate gutters, aligned axes, and shared labels where useful. Do not create a 90 mm panel and stretch it to 185 mm without reviewing typography and density.

### Presentation

Choose the actual on-slide size first and enlarge typography, strokes, and markers for the viewing distance. Preserve the same visual hierarchy and color roles as the publication profiles, but do not force 6-8 pt publication text onto a projected slide.

### Browser HTML

Treat 90 mm as an export/design baseline rather than a literal browser width. Display a single panel responsively at a comfortable screen width, commonly about 640-760 CSS px on desktop, with a mobile width of `100%`. When the figure must remain editable, use SVG/DOM and the semantic editing contract in [references/editable-html.md](references/editable-html.md); avoid raster-only, Canvas, or WebGL output unless density requires a documented fallback.

For browser SVG and HTML, use the font stack `Calibri, "Microsoft YaHei", sans-serif`. Calibri supplies English glyphs and Microsoft YaHei supplies Chinese fallback glyphs. Keep all rendered figure titles explicitly black.

Editable HTML figures should support wheel or button zoom, left-drag box zoom as the default pointer mode, and an explicit Pan mode whose left-drag moves both axis ranges. Hovering should snap to the nearest raw data point and show a solid focus marker, dashed horizontal and vertical guides, and exact numeric values; clear this transient readout on pointer leave rather than creating persistent selections that require a Clear selection action. Preserve an obvious Reset view path. Panning moves the viewport only; never allow interaction to move a measured data point or silently change its value.

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

- Finishing from source code without rendering and inspecting the actual output.
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
- Hiding box zoom and two-axis pan behind an unexplained drag gesture, or retaining a persistent point selection whose clearing action is not obvious.
- Implementing zoom or pan by scaling text and axes until they become unreadable, or allowing drag interaction to change measured coordinates.

## Tool-specific defaults

### Matplotlib

For a 90 mm publication panel, start from settings like:

```python
plt.rcParams.update({
    "font.family": ["Calibri", "Microsoft YaHei"],
    "font.size": 7,
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
    "figure.dpi": 150,
    "savefig.dpi": 300,
})

mm_to_in = lambda mm: mm / 25.4
fig, ax = plt.subplots(
    figsize=(mm_to_in(90), mm_to_in(58)),
    constrained_layout=True,
)
```

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
