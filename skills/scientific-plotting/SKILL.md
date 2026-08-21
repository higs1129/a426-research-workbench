---
name: scientific-plotting
description: Use whenever creating, updating, or regenerating scientific figures for experiments, measurements, reports, talks, session.md records, or data analysis; ensures plots are readable in meeting-room projection and labels do not obscure data.
---

# Scientific Plotting

## Core Rule

Every new figure should be readable when projected in a meeting room. Prioritize clear communication over packing everything inside the axes.

This skill applies to new plots only unless the user asks to revise old figures.

## Meeting-Room Readability Gate

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

## Layout Checks

Before saving a figure:

1. Check that axis labels and tick labels are not clipped.
2. Check that the legend does not overlap the plotted signal or key annotations.
3. Check that long labels wrap or move outside the axes.
4. Check that the figure still works at slide scale, not only when zoomed in.
5. If there are multiple stages or parameter groups, use color bands or separate panels with a clear external legend.

## Matplotlib Defaults

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

## Measurement Figures

For scope traces, spectra, PID sweeps, and lock timelines:

- Clearly state what each channel means, not only `CH1` or `CH2`.
- Put key numeric settings outside the axes when they are long.
- If showing lock stages, mark stages with readable color bands and a legend outside the data area.
- When plotting an accepted data group for external `session.md`, save both the raw data path and the representative figure path under `$DAILY_NOTE_DATA_ROOT` or a user-provided external output directory. Do not save generated figures into tracked repo paths.
