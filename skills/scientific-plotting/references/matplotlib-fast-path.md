# Matplotlib editable-HTML fast path

Read this reference for ordinary single-linear-axes line, scatter, spectrum, and similar standard data plots requested as editable HTML.

## Boundary

Use this path when Matplotlib can express the scientific figure with one linear axes and `Line2D` or `PathCollection` data series. The task-local code remains ordinary Matplotlib code. The shared renderer owns physical sizing, typography defaults, editable SVG export, HTML assembly, interaction wiring, and optional stage timing.

Use the lower-level [renderer-contract.md](renderer-contract.md) instead for multi-axes figures, logarithmic or broken axes, specialized linked annotations, scientific diagrams, or visual effects that require custom SVG structure. Do not add a permanent chart template merely because one task has unusual data.

## Task-local hook

Keep one small Python generator beside the task data and output. It defines exactly two hooks:

```python
import matplotlib.pyplot as plt
import numpy as np


def load_data():
    data = np.loadtxt("measurement.csv", delimiter=",", skiprows=1)
    return data[:, 0], data[:, 1]


def build_figure(data, profile):
    x, y = data
    fig, ax = plt.subplots(constrained_layout=True)
    line, = ax.plot(x, y, label="Measured transmission")
    ax.set_title("Optical transmission spectrum")
    ax.set_xlabel("Relative frequency (GHz)")
    ax.set_ylabel("Normalized transmission")
    ax.legend(frameon=False)
    return {"figure": fig, "axes": ax, "series": [line]}
```

`load_data()` owns authoritative file reading and transformations. `build_figure(data, profile)` owns the scientific content and returns one Matplotlib `Figure`, its single `Axes`, and the data-bearing `Line2D` or `PathCollection` artists. Use a `Line2D` with `linestyle="none"` and a marker, or `Axes.scatter`, for standard scatter data.

The shared renderer enforces the selected profile's physical dimensions and common typography. Task code may set scientifically meaningful colors, labels, ranges, legends, annotations, and line roles, but should not duplicate shared font, size, grid, interaction, or HTML defaults.

The shared automatic locator is used only when the task leaves an axis on Matplotlib's default `AutoLocator`. An explicit `MultipleLocator` or `FixedLocator` is authoritative: the renderer preserves it in the initial SVG and serializes a fixed-step or fixed-values policy so browser zoom and pan redraw the same intended ticks. Use this for requirements such as an exact `0.2` y-axis interval; do not approximate a fixed interval through `MaxNLocator`.

## Render command

Use explicit task paths:

```powershell
python scripts/render_matplotlib_editable.py `
  --plot-script path/to/task_plot.py `
  --profile-id 90mm-single `
  --output path/to/figure.html
```

For a broad multi-feature scan that genuinely requires double-column width, select `185mm-wide` at generation time. Do not expose a delivery-profile selector in the resulting HTML.

When execution time is being diagnosed or the user requests timing, add:

```powershell
  --timing-output path/to/figure-timing.json
```

The report records:

- shared setup and task-module loading;
- task data loading;
- Matplotlib figure construction;
- editable SVG export;
- HTML/runtime assembly;
- output writing;
- total renderer time.

Do not produce timing reports during ordinary figure generation unless requested.

## Output behavior

The renderer sets `svg.fonttype = "none"`, so ordinary title, label, tick, and legend text remain SVG `<text>` nodes instead of glyph paths. The final HTML embeds:

- the Matplotlib SVG rather than a raster image;
- the authoritative data series needed for hover and viewport changes;
- exactly one delivery profile;
- the shared interaction runtime and Matplotlib bridge;
- visible box zoom, pan, reset, hover readout, compact presentation controls, an `Edit layout` mode for whole-bounds selection and movement of the title, axis labels, legend, and collective x/y numeric tick-label groups without moving tick marks or scientific geometry, bounded layout undo, and clean SVG export.

The selected profile also supplies a compact `0.28 em` major-tick-to-number gap, a `0.25 em` top-legend-to-axis gap, a `0.25 em` title-to-top-legend gap, and a small `0.4 em` top safety reserve for browser font-metric differences. The renderer measures the Matplotlib title and legend text bounding boxes after the canvas draw. When a horizontal top legend collides with the title, it records a deterministic layout offset that places the title above the legend and, when needed, reduces the axes height just enough to reserve the top band; if the fixed canvas cannot contain that resolved stack, generation stops with an actionable error instead of silently emitting an overlap. Because browser font metrics can differ slightly from Matplotlib, the bridge performs one bounded `getBoundingClientRect()` check and adds only the residual title offset required by the same profile gap. This automatic correction is disabled as soon as the user manually moves the title or legend, so direct editing remains authoritative. The bridge also reuses the profile tokens and serialized tick policy during interactive redraw instead of introducing separate browser-only defaults.

The output is self-contained and has no runtime dependency on the Skill directory or a network connection. The task-local Python generator remains the reproducible maintenance entry point.

During ordinary figure production, validate the generated file with cheap structural and numeric assertions and stop. Do not open a browser for a generic visual pass. Use targeted browser assertions only when the user requests visual validation, a deterministic check exposes an unresolved layout risk, a complex/custom figure requires it, or this shared renderer is being developed.

## Fast-path failure behavior

Stop and use the custom SVG route when the renderer reports multiple axes, an unsupported artist type, or a scale/interaction requirement outside this contract. Do not force a complex figure through the standard bridge, and do not silently rasterize unsupported scientific geometry.

## Representative test

When this reusable fast path is changed or the user explicitly requests testing, run:

```powershell
python tests/test_matplotlib_fast_path.py
```

The maintained fixture and timing report remain under `tests/fixtures/`. Ordinary figure tasks must not run or regenerate this test.
