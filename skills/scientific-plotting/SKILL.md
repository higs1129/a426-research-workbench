---
name: scientific-plotting
description: Creates, updates, or regenerates scientific figures for experiments, measurements, reports, talks, session records, and data analysis with projection-readable layout and traceable visual choices. Use when a figure is an intended output or an existing figure must be revised. Do not use for interpreting an unchanged figure, general image editing, or decorative illustration.
metadata:
  version: "1.0"
  skill-author: "Personal Research Workflow"
---

# Scientific Plotting

## Purpose and boundaries

Every new figure should be readable when projected in a meeting room. Prioritize clear communication over packing everything inside the axes.

This skill applies to new plots only unless the user asks to revise old figures.

It governs visual construction and verification, not the scientific interpretation of unchanged figures. Preserve data provenance and do not let styling, smoothing, or annotation imply evidence the data do not contain.

## When to use

- Use for a new or revised scientific plot, multipanel figure, quicklook, report figure, slide figure, or `session.md` figure.
- Use when plotting choices affect raw/processed data distinction, units, uncertainty, readability, or visual emphasis.
- Do not use when the task is only to explain an existing figure, edit a photograph, create decorative artwork, or write prose without producing a figure.

## Reproducible workflow

1. Identify the scientific question, intended audience, output format, target display size, data source, units, and whether the figure is exploratory or final.
2. Inspect the authoritative data and distinguish raw values, transformations, fits, smoothing, uncertainty, and annotations.
3. Choose the smallest layout that communicates the comparison without covering data or shrinking text; split panels when necessary.
4. Generate the figure with explicit labels, units, visual hierarchy, and output path outside tracked repositories when the figure is a research artifact.
5. Render the actual PNG, SVG, PDF, or HTML and inspect it at its intended scale.
6. Apply the validation gate below and revise until no material clipping, overlap, ambiguity, or misleading emphasis remains.

## Evidence and visual validation

Treat readability as a hard gate for every report, weekly-summary, monthly-summary, and meeting figure. A figure is not finished until it can be read at normal browser zoom or slide scale without zooming into the page.

- Do not shrink fonts to fit more traces, panels, captions, or legend text. Split into more panels, move legends outside the axes, or reduce the number of visible traces.
- Use black, bold axis labels and tick labels by default. Gray text is acceptable only for secondary captions or de-emphasized notes outside the main data area.
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

## Default Figure Style

- Use large fonts by default:
  - title: 20-24 pt
  - axis labels: 18-22 pt
  - tick labels: 16-18 pt
  - legend/text annotations: 15-18 pt
- Use sufficiently thick lines and markers:
  - line width: at least 2 px for main traces
  - raw trace with smoothing overlay: about 2.4-2.8 px with 0.4-0.6 opacity
  - smoothed/fitted trace: about 1.5-1.8 px with 0.9-1.0 opacity
  - marker size: at least 6-8 px when markers matter
- Use high enough output resolution:
  - PNG: at least 180-300 dpi for reports or slides
  - SVG/PDF is preferred when the downstream document supports vector figures
- Keep color choices distinguishable on a projector and in grayscale when possible.

## Labels And Legends

- Do not let legends, text boxes, or parameter labels cover important curves, peaks, dips, ticks, grid labels, or annotations.
- If a legend or parameter description is long, place it outside the plotting axes, usually on the right or below the plot.
- Put detailed run parameters in the caption, side panel, or session text instead of inside the data area.
- Prefer concise labels in the figure and fuller explanations in `session.md`.

### Layout checks

Before saving a figure:

1. Check that axis labels and tick labels are not clipped.
2. Check that the legend does not overlap the plotted signal or key annotations.
3. Check that long labels wrap or move outside the axes.
4. Check that the figure still works at slide scale, not only when zoomed in.
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

## Tool-specific defaults

### Matplotlib

When using Matplotlib, start from settings like:

```python
plt.rcParams.update({
    "font.size": 16,
    "axes.titlesize": 22,
    "axes.labelsize": 20,
    "xtick.labelsize": 17,
    "ytick.labelsize": 17,
    "legend.fontsize": 16,
    "axes.labelweight": "bold",
    "axes.titleweight": "bold",
    "font.weight": "bold",
    "lines.linewidth": 2.4,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})
```

For long legends:

```python
fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0)
```

If the external legend needs more room, enlarge the figure instead of shrinking fonts.

### Measurement figures

For scope traces, spectra, PID sweeps, and lock timelines:

- Clearly state what each channel means, not only `CH1` or `CH2`.
- Put key numeric settings outside the axes when they are long.
- If showing lock stages, mark stages with readable color bands and a legend outside the data area.
- When plotting an accepted data group for external `session.md`, save both the raw data path and the representative figure path under `$DAILY_NOTE_DATA_ROOT` or a user-provided external output directory. Do not save generated figures into tracked repo paths.
