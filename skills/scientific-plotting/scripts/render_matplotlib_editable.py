"""Render a standard single-axes Matplotlib figure as editable offline HTML.

The task-local plot module supplies two small hooks:

    load_data() -> any
    build_figure(data, profile) -> {"figure": fig, "axes": ax, "series": [...]}

The shared renderer owns the physical profile, editable SVG export, HTML shell,
interaction bridge, and optional stage timing. Complex multi-axes or custom SVG
figures should use the lower-level renderer contract instead.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from io import StringIO
from pathlib import Path
from time import perf_counter
from types import ModuleType
from typing import Any, Iterable

import matplotlib as mpl
from matplotlib import colors as mpl_colors
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoLocator, FixedLocator, MaxNLocator, MultipleLocator

from bundle_editable_figure import bundle_text, load_profile


SKILL_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = SKILL_ROOT / "assets" / "matplotlib-svg-bridge.js"


def elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def load_plot_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("scientific_plot_task", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load plot module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply_profile(profile: dict[str, Any]) -> None:
    mpl.rcParams.update(
        {
            "font.family": ["Calibri", "Microsoft YaHei"],
            "font.size": profile["tickPt"],
            "axes.titlesize": profile["figureTitlePt"],
            "axes.titlecolor": "black",
            "axes.titleweight": "bold",
            "axes.labelsize": profile["axisLabelPt"],
            "axes.labelcolor": "black",
            "axes.labelweight": "bold",
            "axes.linewidth": profile["axisWidthPt"],
            "axes.grid": False,
            "xtick.labelsize": profile["tickPt"],
            "ytick.labelsize": profile["tickPt"],
            "xtick.color": "black",
            "ytick.color": "black",
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.pad": profile["tickLabelGapEm"] * profile["tickPt"],
            "ytick.major.pad": profile["tickLabelGapEm"] * profile["tickPt"],
            "legend.fontsize": profile["legendPt"],
            "legend.labelcolor": "black",
            "lines.linewidth": profile["rawWidthPt"],
            "text.color": "black",
            "svg.fonttype": "none",
            "figure.dpi": 150,
            "savefig.dpi": 300,
        }
    )


def normalize_result(value: Any) -> tuple[Figure, Axes, list[Any]]:
    if not isinstance(value, dict):
        raise SystemExit("build_figure() must return a dict with figure, axes, and optional series.")
    figure = value.get("figure")
    axes = value.get("axes")
    if not isinstance(figure, Figure) or not isinstance(axes, Axes):
        raise SystemExit("build_figure() did not return Matplotlib figure and axes objects.")
    if len(figure.axes) != 1:
        raise SystemExit(
            "The Matplotlib fast path supports one linear axes. Use the custom SVG contract "
            "for multi-axes or structurally complex figures."
        )
    series = list(value.get("series") or axes.lines or [])
    if not series:
        series = list(axes.collections)
    if not series:
        raise SystemExit("No Line2D or PathCollection series were declared or found.")
    return figure, axes, series


def finite_list(values: Iterable[Any]) -> list[float | None]:
    result: list[float | None] = []
    for value in values:
        number = float(value)
        result.append(number if math.isfinite(number) else None)
    return result


def dash_pattern(line_style: Any) -> str:
    return {
        "--": "6 4",
        "dashed": "6 4",
        "-.": "6 3 1.5 3",
        "dashdot": "6 3 1.5 3",
        ":": "1.5 3",
        "dotted": "1.5 3",
    }.get(str(line_style), "")


def line_payload(artist: Line2D, index: int) -> dict[str, Any]:
    artist.set_gid(f"sf-mpl-series-{index}")
    return {
        "id": f"sf-series-{index}",
        "sourceId": f"sf-mpl-series-{index}",
        "type": "line" if artist.get_linestyle() not in ("", "None", "none") else "scatter",
        "label": artist.get_label() if not artist.get_label().startswith("_") else f"Series {index + 1}",
        "x": finite_list(artist.get_xdata(orig=False)),
        "y": finite_list(artist.get_ydata(orig=False)),
        "color": mpl_colors.to_hex(artist.get_color(), keep_alpha=False),
        "opacity": float(artist.get_alpha() if artist.get_alpha() is not None else 1.0),
        "lineWidthPt": float(artist.get_linewidth()),
        "dash": dash_pattern(artist.get_linestyle()),
        "markerPt": float(artist.get_markersize()),
    }


def collection_payload(artist: PathCollection, index: int) -> dict[str, Any]:
    artist.set_gid(f"sf-mpl-series-{index}")
    offsets = artist.get_offsets()
    colors = artist.get_facecolors()
    sizes = artist.get_sizes()
    color = mpl_colors.to_hex(colors[0], keep_alpha=False) if len(colors) else "#4c84b5"
    marker_pt = math.sqrt(float(sizes[0])) if len(sizes) else 5.0
    return {
        "id": f"sf-series-{index}",
        "sourceId": f"sf-mpl-series-{index}",
        "type": "scatter",
        "label": artist.get_label() if not artist.get_label().startswith("_") else f"Series {index + 1}",
        "x": finite_list(offsets[:, 0]),
        "y": finite_list(offsets[:, 1]),
        "color": color,
        "opacity": float(artist.get_alpha() if artist.get_alpha() is not None else 1.0),
        "lineWidthPt": 0.0,
        "dash": "",
        "markerPt": marker_pt,
    }


def series_payload(artists: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, artist in enumerate(artists):
        if isinstance(artist, Line2D):
            payload.append(line_payload(artist, index))
        elif isinstance(artist, PathCollection):
            payload.append(collection_payload(artist, index))
        else:
            raise SystemExit(
                f"Unsupported standard-series artist {type(artist).__name__}; "
                "use Line2D, PathCollection, or the custom SVG path."
            )
    return payload


def _use_shared_locator(axis: Any, *, minimum_ticks: int) -> None:
    """Install the shared automatic locator without replacing explicit fixed ticks."""

    locator = axis.get_major_locator()
    if isinstance(locator, (MultipleLocator, FixedLocator)):
        return
    if type(locator) is AutoLocator:
        axis.set_major_locator(
            MaxNLocator(
                nbins=5,
                steps=[1, 2, 2.5, 5, 10],
                min_n_ticks=minimum_ticks,
            )
        )


def _fixed_step_policy(axis: Any) -> dict[str, Any]:
    locations = sorted(
        {
            float(value)
            for value in axis.get_majorticklocs()
            if math.isfinite(float(value))
        }
    )
    differences = [
        right - left
        for left, right in zip(locations, locations[1:])
        if right - left > 0
    ]
    if not differences:
        raise SystemExit("A MultipleLocator must yield at least two finite major ticks.")
    step = min(differences)
    tolerance = max(1e-12, abs(step) * 1e-8)
    if any(abs(difference - step) > tolerance for difference in differences):
        raise SystemExit("A fixed-step major locator yielded non-uniform tick spacing.")
    step = float(f"{step:.12g}")
    reference = float(f"{min(locations, key=abs):.12g}")
    return {
        "mode": "fixed-step",
        "step": step,
        "reference": reference,
    }


def tick_policies(axes: Axes, profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    policies: dict[str, dict[str, Any]] = {}
    for name, axis in (("x", axes.xaxis), ("y", axes.yaxis)):
        locator = axis.get_major_locator()
        if isinstance(locator, MultipleLocator):
            policies[name] = _fixed_step_policy(axis)
        elif isinstance(locator, FixedLocator):
            policies[name] = {
                "mode": "fixed-values",
                "values": [
                    float(value)
                    for value in axis.get_majorticklocs()
                    if math.isfinite(float(value))
                ],
            }
        else:
            policies[name] = {
                "mode": "nice",
                "targetCount": int(profile["majorTickTarget"]),
            }
    return policies


def prepare_figure(figure: Figure, axes: Axes, profile: dict[str, Any], artists: list[Any]) -> None:
    figure.set_size_inches(
        profile["exportWidthMm"] / 25.4,
        profile["exportHeightMm"] / 25.4,
        forward=True,
    )
    axes.grid(False)
    for spine in axes.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(profile["axisWidthPt"])
    # Style the existing Text object directly. Calling set_title() here would reset
    # a task-supplied title position or padding after the task has built the figure.
    axes.title.set_color("black")
    axes.title.set_fontweight("bold")
    axes.xaxis.label.set_color("black")
    axes.yaxis.label.set_color("black")
    axes.xaxis.label.set_fontweight("bold")
    axes.yaxis.label.set_fontweight("bold")
    axes.title.set_gid("sf-figure-title")
    axes.xaxis.label.set_gid("sf-x-axis-label")
    axes.yaxis.label.set_gid("sf-y-axis-label")
    legend = axes.get_legend() or (figure.legends[0] if figure.legends else None)
    if legend is not None:
        legend.set_gid("sf-legend")
    _use_shared_locator(axes.xaxis, minimum_ticks=5)
    _use_shared_locator(axes.yaxis, minimum_ticks=4)
    axes.xaxis.labelpad = profile["axisLabelPt"] * profile["axisTitleGapEmX"]
    axes.yaxis.labelpad = profile["axisLabelPt"] * profile["axisTitleGapEmY"]
    for label in [*axes.get_xticklabels(), *axes.get_yticklabels()]:
        label.set_color("black")
        label.set_fontweight("bold")
    series_payload(artists)
    figure.canvas.draw()


def plot_bounds(figure: Figure, axes: Axes) -> dict[str, float]:
    bbox = axes.get_window_extent()
    scale = 72.0 / figure.dpi
    height_pt = figure.get_figheight() * 72.0
    return {
        "left": round(bbox.x0 * scale, 4),
        "right": round(bbox.x1 * scale, 4),
        "top": round(height_pt - bbox.y1 * scale, 4),
        "bottom": round(height_pt - bbox.y0 * scale, 4),
    }


def layout_defaults(
    figure: Figure,
    axes: Axes,
    profile: dict[str, Any],
    *,
    allow_top_reserve: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults: dict[str, Any] = {
        "title": {"x": 0.0, "y": 0.0},
        "xLabel": {"x": 0.0, "y": 0.0},
        "yLabel": {"x": 0.0, "y": 0.0},
        "legend": {"x": 0.0, "y": 0.0},
    }
    legend = axes.get_legend() or (figure.legends[0] if figure.legends else None)
    if legend is None:
        return defaults, {"titleLegend": {"status": "not-applicable"}}
    renderer = figure.canvas.get_renderer()
    axes_box = axes.get_window_extent(renderer)
    visible_boxes = [
        text.get_window_extent(renderer)
        for text in legend.get_texts()
        if text.get_visible() and text.get_text()
    ]
    if not visible_boxes:
        return defaults, {"titleLegend": {"status": "not-applicable"}}
    current_gap_px = min(box.y0 for box in visible_boxes) - axes_box.y1
    desired_gap_px = (
        profile["legendAxisGapEm"] * profile["legendPt"] * figure.dpi / 72.0
    )
    move_down_px = max(0.0, current_gap_px - desired_gap_px)
    defaults["legend"]["y"] = round(move_down_px * 72.0 / figure.dpi, 4)

    title_box = axes.title.get_window_extent(renderer)
    legend_box = legend.get_window_extent(renderer)
    projected_legend_text_top = max(box.y1 for box in visible_boxes) - move_down_px
    horizontal_overlap = bool(
        min(title_box.x1, legend_box.x1) > max(title_box.x0, legend_box.x0)
    )
    desired_title_gap_px = (
        profile["titleLegendGapEm"]
        * profile["figureTitlePt"]
        * figure.dpi
        / 72.0
    )
    required_title_up_px = (
        projected_legend_text_top + desired_title_gap_px - title_box.y0
        if horizontal_overlap and axes.title.get_text()
        else 0.0
    )
    required_title_up_px = max(0.0, required_title_up_px)
    status = "clear"
    if required_title_up_px > 0:
        projected_title_top = title_box.y1 + required_title_up_px
        desired_top_reserve_px = (
            profile["topLayoutSafetyEm"]
            * profile["figureTitlePt"]
            * figure.dpi
            / 72.0
        )
        current_top_reserve_px = figure.bbox.y1 - projected_title_top
        reserve_deficit_px = desired_top_reserve_px - current_top_reserve_px
        if allow_top_reserve and reserve_deficit_px > 0:
            position = axes.get_position()
            reserve_fraction = reserve_deficit_px / figure.bbox.height
            if position.height - reserve_fraction <= 0.2:
                raise SystemExit(
                    "The title and top legend require more vertical room than the fixed "
                    "canvas can reserve without collapsing the plot. Increase figure height "
                    "or wrap the legend."
                )
            axes.set_position(
                [
                    position.x0,
                    position.y0,
                    position.width,
                    position.height - reserve_fraction,
                ]
            )
            figure.canvas.draw()
            return layout_defaults(
                figure,
                axes,
                profile,
                allow_top_reserve=False,
            )
        if projected_title_top > figure.bbox.y1 + 0.5:
            raise SystemExit(
                "The title and top legend overlap, but the fixed canvas has insufficient "
                "top margin for deterministic separation. Increase figure height, shorten "
                "the title, wrap the legend, or place the legend outside the top band."
            )
        defaults["title"]["y"] = round(
            -required_title_up_px * 72.0 / figure.dpi,
            4,
        )
        status = "adjusted"

    diagnostics = {
        "titleLegend": {
            "status": status,
            "horizontalOverlap": horizontal_overlap,
            "legendShiftPt": defaults["legend"]["y"],
            "titleShiftPt": defaults["title"]["y"],
            "targetGapPt": round(
                profile["titleLegendGapEm"] * profile["figureTitlePt"],
                4,
            ),
            "topReservePt": round(
                max(0.0, figure.bbox.y1 - (title_box.y1 + required_title_up_px))
                * 72.0
                / figure.dpi,
                4,
            ),
        }
    }
    return defaults, diagnostics


def export_svg(figure: Figure) -> str:
    buffer = StringIO()
    figure.savefig(buffer, format="svg", metadata={"Creator": "scientific-plotting"})
    raw = buffer.getvalue()
    start = raw.find("<svg")
    if start < 0:
        raise SystemExit("Matplotlib did not produce an SVG root element.")
    return raw[start:]


def add_interaction_layers(svg: str, bounds: dict[str, float]) -> str:
    marker = "</svg>"
    index = svg.rfind(marker)
    if index < 0:
        raise SystemExit("Generated SVG is missing its closing tag.")
    width = bounds["right"] - bounds["left"]
    height = bounds["bottom"] - bounds["top"]
    overlay = f"""
  <defs data-sf-editor-only="true">
    <clipPath id="sf-plot-clip"><rect x="{bounds['left']}" y="{bounds['top']}" width="{width}" height="{height}"/></clipPath>
  </defs>
  <g id="sf-dynamic-geometry" clip-path="url(#sf-plot-clip)"></g>
  <g id="sf-dynamic-ticks"></g>
  <g id="inspection-overlay" class="sf-transient" visibility="hidden"></g>
  <rect id="zoom-brush" class="sf-transient" visibility="hidden"></rect>
  <rect id="interaction-surface" data-sf-interaction-surface="true"
        x="{bounds['left']}" y="{bounds['top']}" width="{width}" height="{height}"
        fill="transparent" pointer-events="all" tabindex="0"/>
"""
    return svg[:index] + overlay + svg[index:]


def html_shell(svg: str, screen_width_px: int) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Editable scientific figure</title>
<style>
:root {{ font-family: Calibri, "Microsoft YaHei", sans-serif; color: #000; background: #f4f6f8; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 16px; }}
.sf-page {{ max-width: {screen_width_px + 340}px; margin: 0 auto; display: grid; grid-template-columns: minmax(0, {screen_width_px}px) 300px; gap: 16px; }}
.sf-card {{ background: #fff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 12px; }}
.sf-toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }}
button, input, select {{ font: inherit; }}
button {{ border: 1px solid #94a3b8; background: #fff; color: #000; border-radius: 6px; padding: 6px 10px; cursor: pointer; }}
button[aria-pressed="true"] {{ background: #165f8f; color: #fff; }}
.sf-status {{ min-height: 1.5em; margin: 4px 0 8px; color: #1f2937; }}
.sf-figure-host svg {{ display: block; width: 100%; height: auto; overflow: visible; touch-action: none; }}
#interaction-surface.sf-pan-mode {{ cursor: grab; }}
#interaction-surface:not(.sf-pan-mode) {{ cursor: crosshair; }}
.sf-layout-editing [data-sf-layout-role] {{ cursor: move; }}
[data-sf-layout-hit] {{ fill: transparent; stroke: none; pointer-events: none; }}
.sf-layout-editing [data-sf-layout-hit] {{ pointer-events: all; }}
[data-sf-selected="true"] > [data-sf-layout-hit] {{ stroke: #0f766e; stroke-width: .8; stroke-dasharray: 3 2; vector-effect: non-scaling-stroke; }}
[data-sf-selected="true"] {{ filter: drop-shadow(0 0 1.5px #0f766e); }}
#zoom-brush {{ fill: rgba(22, 95, 143, .14); stroke: #165f8f; stroke-width: 1; stroke-dasharray: 4 3; pointer-events: none; }}
.sf-editor label {{ display: grid; gap: 4px; margin: 0 0 10px; font-weight: 700; }}
.sf-editor input, .sf-editor select {{ width: 100%; padding: 6px; border: 1px solid #94a3b8; border-radius: 5px; }}
.sf-editor h2 {{ margin: 0 0 12px; font-size: 18px; }}
.sf-layout-inspector {{ margin: 14px 0; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; }}
.sf-layout-inspector legend {{ padding: 0 4px; font-weight: 700; }}
#sf-layout-selection {{ min-height: 1.5em; margin-bottom: 8px; color: #0f766e; font-weight: 700; }}
@media (max-width: 900px) {{ .sf-page {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<main class="sf-page" id="figure-root" data-sf-root>
  <section class="sf-card">
    <div class="sf-toolbar">
      <button data-sf-action="box-zoom" aria-pressed="true">Box zoom</button>
      <button data-sf-action="pan" aria-pressed="false">Pan</button>
      <button data-sf-action="zoom-in">Zoom +</button>
      <button data-sf-action="zoom-out">Zoom −</button>
      <button data-sf-action="reset-view">Reset view</button>
      <button data-sf-action="edit-layout" aria-pressed="false">Edit layout</button>
      <button data-sf-action="undo-layout" disabled>Undo layout</button>
      <button data-sf-action="export-svg">Export SVG</button>
    </div>
    <div class="sf-status" id="sf-status">Hover to read a raw point. Left-drag boxes a zoom region.</div>
    <div class="sf-figure-host">{svg}</div>
  </section>
  <aside class="sf-card sf-editor">
    <h2>Figure editor</h2>
    <label>Figure title<input data-sf-field="title" type="text"></label>
    <label>X-axis label<input data-sf-field="xLabel" type="text"></label>
    <label>Y-axis label<input data-sf-field="yLabel" type="text"></label>
    <label>Font family<select data-sf-field="fontFamily"><option value='Calibri, "Microsoft YaHei", sans-serif'>Calibri / Microsoft YaHei</option><option value='Arial, "Microsoft YaHei", sans-serif'>Arial / Microsoft YaHei</option></select></label>
    <label>Plot text (pt)<input data-sf-field="plotFontPt" type="number" min="5" max="30" step="0.5"></label>
    <label>Title (pt)<input data-sf-field="titleFontPt" type="number" min="5" max="30" step="0.5"></label>
    <label>Data line (pt)<input data-sf-field="lineWidthPt" type="number" min="0.2" max="8" step="0.1"></label>
    <fieldset class="sf-layout-inspector">
      <legend>Selected element</legend>
      <div id="sf-layout-selection">None</div>
      <label>Horizontal offset<input data-sf-layout-field="x" type="number" step="0.5" disabled></label>
      <label>Vertical offset<input data-sf-layout-field="y" type="number" step="0.5" disabled></label>
    </fieldset>
    <button data-sf-action="restore-style">Restore defaults</button>
  </aside>
  <!-- SCIENTIFIC_FIGURE_PROFILE -->
  <!-- SCIENTIFIC_FIGURE_DATA -->
  <!-- SCIENTIFIC_FIGURE_RUNTIME -->
  <!-- SCIENTIFIC_FIGURE_ADAPTER -->
</main>
</body>
</html>
"""


def figure_data(
    figure: Figure,
    axes: Axes,
    artists: list[Any],
    profile: dict[str, Any],
    profile_id: str,
    initial_layout: dict[str, Any],
    layout_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    x_min, x_max = map(float, axes.get_xlim())
    y_min, y_max = map(float, axes.get_ylim())
    return {
        "renderer": "matplotlib-svg-fast-path",
        "profileId": profile_id,
        "figureId": f"matplotlib-{profile_id}",
        "plotBounds": plot_bounds(figure, axes),
        "fullView": {"xMin": x_min, "xMax": x_max, "yMin": y_min, "yMax": y_max},
        "labels": {
            "title": axes.get_title(),
            "x": axes.get_xlabel(),
            "y": axes.get_ylabel(),
        },
        "ticks": tick_policies(axes, profile),
        "layoutDefaults": initial_layout,
        "layoutDiagnostics": layout_diagnostics,
        "series": series_payload(artists),
    }


def render(args: argparse.Namespace) -> dict[str, Any]:
    total_start = perf_counter()
    timings: dict[str, float] = {}

    stage = perf_counter()
    profile = load_profile(args.profile_id)
    apply_profile(profile)
    module = load_plot_module(args.plot_script.resolve())
    timings["setup_and_module_load_ms"] = elapsed_ms(stage)

    if not hasattr(module, "load_data") or not hasattr(module, "build_figure"):
        raise SystemExit("Plot module must define load_data() and build_figure(data, profile).")

    stage = perf_counter()
    data = module.load_data()
    timings["data_load_ms"] = elapsed_ms(stage)

    stage = perf_counter()
    figure, axes, artists = normalize_result(module.build_figure(data, profile))
    prepare_figure(figure, axes, profile, artists)
    initial_layout, layout_diagnostics = layout_defaults(figure, axes, profile)
    timings["matplotlib_build_ms"] = elapsed_ms(stage)

    stage = perf_counter()
    svg = add_interaction_layers(export_svg(figure), plot_bounds(figure, axes))
    payload = figure_data(
        figure,
        axes,
        artists,
        profile,
        args.profile_id,
        initial_layout,
        layout_diagnostics,
    )
    timings["svg_export_ms"] = elapsed_ms(stage)

    stage = perf_counter()
    bridge = BRIDGE_PATH.read_text(encoding="utf-8")
    shell = html_shell(svg, int(profile["screenWidthPx"]))
    html = bundle_text(shell=shell, adapter=bridge, data=payload, profile_id=args.profile_id)
    timings["html_assembly_ms"] = elapsed_ms(stage)

    stage = perf_counter()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8", newline="\n")
    timings["output_write_ms"] = elapsed_ms(stage)
    timings["total_ms"] = elapsed_ms(total_start)

    report = {
        "plotScript": str(args.plot_script.resolve()),
        "output": str(output),
        "profileId": args.profile_id,
        "seriesCount": len(artists),
        "pointCount": sum(len(item["x"]) for item in payload["series"]),
        "timings": timings,
    }
    if args.timing_output:
        timing_output = args.timing_output.resolve()
        timing_output.parent.mkdir(parents=True, exist_ok=True)
        timing_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a standard Matplotlib figure as editable offline HTML."
    )
    parser.add_argument("--plot-script", type=Path, required=True)
    parser.add_argument("--profile-id", required=True, choices=["90mm-single", "185mm-wide"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timing-output", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    render(parse_args())
