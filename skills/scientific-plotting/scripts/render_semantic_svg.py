#!/usr/bin/env python3
"""Render an explicit scientific figure model as standard semantic SVG."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from bundle_editable_figure import load_profile


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
PROFILE_WIDTH_MM = {
    "90mm-single": 90.0,
    "185mm-double": 185.0,
    "185mm-composite": 185.0,
}
SOURCE_CONFIDENCE = {
    "authoritative-data": "exact",
    "inline-data-html": "exact",
    "canvas-reconstruction": "approximate",
}
COLORS = ("#000000", "#d90429", "#0067a5", "#169b45")
PT_TO_MM = 25.4 / 72.0
PROFILE_LAYOUT = {
    "90mm-single": {
        "margins": {"left": 13.0, "right": 5.0, "top": 5.0, "bottom": 12.0},
    },
    "185mm-double": {
        "margins": {"left": 20.0, "right": 8.0, "top": 8.0, "bottom": 18.0},
    },
    "185mm-composite": {
        "margins": {"left": 20.0, "right": 8.0, "top": 8.0, "bottom": 18.0},
    },
}


class ModelError(ValueError):
    pass


def svg_tag(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def safe_id(value: object, label: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value).strip()).strip("-.")
    if not result:
        raise ModelError(f"{label} requires a stable id")
    if not re.match(r"[A-Za-z_]", result):
        result = f"fig-{result}"
    return result


def finite_number(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ModelError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ModelError(f"{label} must be finite")
    return result


def validate_finite(value: object, label: str = "model") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        finite_number(value, label)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_finite(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            validate_finite(item, f"{label}.{key}")


def validate_axis(axis: object, name: str) -> dict:
    if not isinstance(axis, dict):
        raise ModelError(f"{name} axis must be an object")
    domain = axis.get("domain")
    if not isinstance(domain, list) or len(domain) != 2:
        raise ModelError(f"{name}.domain must contain two numbers")
    start, end = (finite_number(domain[0], f"{name}.domain[0]"), finite_number(domain[1], f"{name}.domain[1]"))
    if start == end:
        raise ModelError(f"{name}.domain endpoints must differ")
    scale = axis.get("scale", "linear")
    if scale not in {"linear", "log"}:
        raise ModelError(f"{name}.scale must be linear or log")
    if scale == "log" and min(start, end) <= 0:
        raise ModelError(f"{name}.domain must be positive for log scale")
    if not str(axis.get("title", "")).strip():
        raise ModelError(f"{name}.title is required")
    return axis


def validate_model(model: object) -> dict:
    if not isinstance(model, dict):
        raise ModelError("figure model root must be an object")
    validate_finite(model)
    safe_id(model.get("figureId", ""), "figureId")
    profile = model.get("profile")
    if profile not in PROFILE_WIDTH_MM:
        raise ModelError(f"profile must be one of {', '.join(PROFILE_WIDTH_MM)}")
    if finite_number(model.get("heightMm"), "heightMm") <= 0:
        raise ModelError("heightMm must be positive")
    source = model.get("sourceOrigin")
    confidence = model.get("coordinateConfidence")
    if source not in SOURCE_CONFIDENCE:
        raise ModelError("sourceOrigin is unsupported")
    if confidence != SOURCE_CONFIDENCE[source]:
        raise ModelError(f"{source} requires coordinateConfidence={SOURCE_CONFIDENCE[source]}")
    validate_axis(model.get("x"), "x")
    validate_axis(model.get("y"), "y")
    series = model.get("series", [])
    if not isinstance(series, list):
        raise ModelError("series must be an array")
    if not series and not model.get("rasterField"):
        raise ModelError("at least one series or rasterField is required")
    seen: set[str] = set()
    for index, item in enumerate(series):
        if not isinstance(item, dict):
            raise ModelError(f"series[{index}] must be an object")
        series_id = safe_id(item.get("id", ""), f"series[{index}].id")
        if series_id in seen:
            raise ModelError(f"duplicate series id: {series_id}")
        seen.add(series_id)
        if item.get("kind", "polyline") not in {"polyline", "scatter", "point-line"}:
            raise ModelError(f"series[{index}].kind must be polyline, scatter, or point-line")
        points = item.get("points")
        if not isinstance(points, list) or not points:
            raise ModelError(f"series[{index}].points must be a non-empty array")
        for point_index, point in enumerate(points):
            if not isinstance(point, list) or len(point) != 2:
                raise ModelError(f"series[{index}].points[{point_index}] must be [x,y]")
            finite_number(point[0], "point x")
            finite_number(point[1], "point y")
    field = model.get("rasterField")
    if field is not None:
        if not isinstance(field, dict) or not str(field.get("href", "")).startswith("data:image/"):
            raise ModelError("rasterField requires an embedded data:image URI")
        if field.get("kind") not in {"continuous", "categorical"}:
            raise ModelError("rasterField.kind must be continuous or categorical")
        for key in ("pixelWidth", "pixelHeight"):
            if finite_number(field.get(key), f"rasterField.{key}") <= 0:
                raise ModelError(f"rasterField.{key} must be positive")
    return model


def nice_ticks(start: float, end: float, count: int = 6) -> list[float]:
    low, high = sorted((start, end))
    rough = (high - low) / max(1, count - 1)
    exponent = math.floor(math.log10(rough))
    fraction = rough / (10**exponent)
    step_fraction = next(candidate for candidate in (1, 2, 2.5, 5, 10) if fraction <= candidate)
    step = step_fraction * (10**exponent)
    first = math.ceil(low / step - 1e-12) * step
    values = []
    value = first
    while value <= high + step * 1e-9 and len(values) < 100:
        values.append(round(value, max(0, 10 - exponent)))
        value += step
    return values if start < end else list(reversed(values))


def axis_ticks(axis: dict) -> list[float]:
    supplied = axis.get("ticks")
    if supplied is not None:
        if not isinstance(supplied, list) or not supplied:
            raise ModelError("axis ticks must be a non-empty array")
        return [finite_number(value, "tick") for value in supplied]
    start, end = map(float, axis["domain"])
    if axis.get("scale", "linear") == "log":
        lower, upper = sorted((math.floor(math.log10(start)), math.ceil(math.log10(end))))
        ticks = [10.0**power for power in range(lower, upper + 1) if min(start, end) <= 10.0**power <= max(start, end)]
        return ticks if start < end else list(reversed(ticks))
    return nice_ticks(start, end)


def scaled(value: float, axis: dict, pixel_start: float, pixel_end: float) -> float:
    start, end = map(float, axis["domain"])
    if axis.get("scale", "linear") == "log":
        value, start, end = math.log10(value), math.log10(start), math.log10(end)
    ratio = (value - start) / (end - start)
    return pixel_start + ratio * (pixel_end - pixel_start)


def fmt(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) >= 10000 or abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.6g}"


def axis_text(axis: dict) -> str:
    title = str(axis.get("title", "")).strip()
    unit = str(axis.get("unit", "")).strip()
    return f"{title} ({unit})" if unit else title


def add_text(parent: ET.Element, text: str, attributes: dict[str, str]) -> ET.Element:
    element = ET.SubElement(parent, svg_tag("text"), attributes)
    element.text = text
    return element


def render(model: dict, overrides: dict | None = None) -> ET.Element:
    model = validate_model(model)
    overrides = overrides or {}
    figure_id = safe_id(model["figureId"], "figureId")
    width_mm = finite_number(overrides.get("widthMm", PROFILE_WIDTH_MM[model["profile"]]), "widthMm")
    height_mm = finite_number(overrides.get("heightMm", model["heightMm"]), "heightMm")
    # The numeric viewBox matches the physical millimetre viewport. Therefore
    # one SVG user unit is one millimetre at the declared delivery size.
    canvas_w = width_mm
    canvas_h = height_mm
    margins = dict(PROFILE_LAYOUT[model["profile"]]["margins"])
    margins.update({key: finite_number(value, f"margin.{key}") for key, value in overrides.get("margins", {}).items()})
    plot_left, plot_top = margins["left"], margins["top"]
    plot_right, plot_bottom = canvas_w - margins["right"], canvas_h - margins["bottom"]
    if plot_right <= plot_left or plot_bottom <= plot_top:
        raise ModelError("margins leave no positive plot area")

    root = ET.Element(svg_tag("svg"), {
        "id": figure_id,
        "data-role": "scientific-figure",
        "data-profile": str(model["profile"]),
        "data-source-origin": str(model["sourceOrigin"]),
        "data-coordinate-confidence": str(model["coordinateConfidence"]),
        "data-user-unit-mm": "1",
        "data-physical-coordinate-system": "mm-isomorphic",
        "width": f"{width_mm:g}mm",
        "height": f"{height_mm:g}mm",
        "viewBox": f"0 0 {canvas_w:g} {canvas_h:g}",
        "preserveAspectRatio": "xMidYMid meet",
        "aria-label": str(model.get("title") or figure_id),
    })
    metadata = ET.SubElement(root, svg_tag("metadata"), {"data-role": "figure-model"})
    metadata.text = json.dumps(model, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    profile = load_profile("90mm-single" if model["profile"] == "90mm-single" else "185mm-wide")
    style_values = {
        "axisLabelSize": profile["axisLabelPt"] * PT_TO_MM,
        "tickLabelSize": profile["tickPt"] * PT_TO_MM,
        "annotationSize": profile["legendPt"] * PT_TO_MM,
        "dataLineWidth": profile["rawWidthPt"] * PT_TO_MM,
        "axisLineWidth": profile["axisWidthPt"] * PT_TO_MM,
        "tickLength": max(2.5, profile["axisWidthPt"] * 4.5) * PT_TO_MM,
    }
    style_values.update(overrides.get("style", {}))
    style_values.setdefault("markerDiameter", float(style_values["tickLabelSize"]) * 0.5)
    style = ET.SubElement(root, svg_tag("style"), {"data-role": "figure-style"})
    style.text = f"""
svg[data-role='scientific-figure']{{--figure-font-family:Calibri,\"Microsoft YaHei\",sans-serif;--axis-label-size:{style_values['axisLabelSize']}px;--tick-label-size:{style_values['tickLabelSize']}px;--annotation-size:{style_values['annotationSize']}px;--data-line-width:{style_values['dataLineWidth']}px;--marker-diameter:{style_values['markerDiameter']}px;--axis-line-width:{style_values['axisLineWidth']}px;--tick-length:{style_values['tickLength']}px;font-family:var(--figure-font-family);color:#000}}
.axis-label{{font-size:var(--axis-label-size);fill:#000;font-weight:700}}.tick-label{{font-size:var(--tick-label-size);fill:#000;font-weight:400}}.annotation{{font-size:var(--annotation-size);fill:#000}}.data-series{{fill:none;stroke-width:var(--data-line-width)}}.data-marker{{fill:currentColor;stroke:none}}.data-marker[data-default-size='true']{{r:calc(var(--marker-diameter)/2)}}.axis-line,.plot-box{{fill:none;stroke:#000;stroke-width:var(--axis-line-width)}}
""".strip()

    defs = ET.SubElement(root, svg_tag("defs"))
    clip_id = f"{figure_id}-plot-clip"
    clip = ET.SubElement(defs, svg_tag("clipPath"), {"id": clip_id})
    ET.SubElement(clip, svg_tag("rect"), {"x": fmt(plot_left), "y": fmt(plot_top), "width": fmt(plot_right - plot_left), "height": fmt(plot_bottom - plot_top)})
    plot = ET.SubElement(root, svg_tag("g"), {"id": f"{figure_id}-plot-area", "data-role": "plot-area"})
    ET.SubElement(plot, svg_tag("rect"), {"id": f"{figure_id}-plot-box", "data-role": "plot-box", "class": "plot-box", "x": fmt(plot_left), "y": fmt(plot_top), "width": fmt(plot_right - plot_left), "height": fmt(plot_bottom - plot_top)})

    field = model.get("rasterField")
    if field:
        field_group = ET.SubElement(plot, svg_tag("g"), {"id": f"{figure_id}-raster-layer", "data-role": "raster-layer", "clip-path": f"url(#{clip_id})"})
        physical_w = (plot_right - plot_left) / canvas_w * width_mm
        physical_h = (plot_bottom - plot_top) / canvas_h * height_mm
        dpi = min(float(field["pixelWidth"]) / (physical_w / 25.4), float(field["pixelHeight"]) / (physical_h / 25.4))
        ET.SubElement(field_group, svg_tag("image"), {
            "id": f"{figure_id}-raster-field", "data-role": "raster-field",
            "data-field-kind": str(field["kind"]),
            "data-resampling": str(field.get("resampling", "bicubic" if field["kind"] == "continuous" else "nearest")),
            "data-pixel-width": str(field["pixelWidth"]), "data-pixel-height": str(field["pixelHeight"]),
            "data-effective-dpi": f"{dpi:.2f}", "href": str(field["href"]),
            "x": fmt(plot_left), "y": fmt(plot_top), "width": fmt(plot_right - plot_left), "height": fmt(plot_bottom - plot_top),
            "preserveAspectRatio": "none",
        })

    series_layer = ET.SubElement(plot, svg_tag("g"), {"id": f"{figure_id}-series", "data-role": "data-series-layer", "clip-path": f"url(#{clip_id})"})
    for index, series in enumerate(model.get("series", [])):
        series_id = safe_id(series["id"], "series id")
        color = str(series.get("color", COLORS[index % len(COLORS)]))
        kind = str(series.get("kind", "polyline"))
        group = ET.SubElement(series_layer, svg_tag("g"), {"id": f"{figure_id}-series-{series_id}", "data-role": "data-series", "data-series-id": series_id, "data-series-kind": kind, "class": "data-series", "stroke": color, "color": color})
        coords = [(scaled(float(point[0]), model["x"], plot_left, plot_right), scaled(float(point[1]), model["y"], plot_bottom, plot_top)) for point in series["points"]]
        if kind in {"polyline", "point-line"}:
            ET.SubElement(group, svg_tag("polyline"), {"id": f"{figure_id}-{series_id}-path", "points": " ".join(f"{fmt(x)},{fmt(y)}" for x, y in coords)})
        if kind in {"scatter", "point-line"}:
            default_radius = float(style_values["markerDiameter"]) / 2
            for point_index, (x_value, y_value) in enumerate(coords):
                attributes = {"id": f"{figure_id}-{series_id}-point-{point_index}", "class": "data-marker", "data-role": "data-marker", "cx": fmt(x_value), "cy": fmt(y_value), "r": fmt(float(series.get("markerRadius", default_radius)))}
                if "markerRadius" not in series:
                    attributes["data-default-size"] = "true"
                ET.SubElement(group, svg_tag("circle"), attributes)

    axes = ET.SubElement(root, svg_tag("g"), {"id": f"{figure_id}-axes", "data-role": "axes"})
    ticks_x = ET.SubElement(axes, svg_tag("g"), {"id": f"{figure_id}-ticks-x", "data-role": "ticks-x"})
    ticks_y = ET.SubElement(axes, svg_tag("g"), {"id": f"{figure_id}-ticks-y", "data-role": "ticks-y"})
    tick_length = float(style_values["tickLength"])
    for index, value in enumerate(axis_ticks(model["x"])):
        x_value = scaled(value, model["x"], plot_left, plot_right)
        ET.SubElement(ticks_x, svg_tag("line"), {"id": f"{figure_id}-tick-x-{index}", "class": "axis-line", "x1": fmt(x_value), "y1": fmt(plot_bottom), "x2": fmt(x_value), "y2": fmt(plot_bottom + tick_length)})
        add_text(ticks_x, fmt(value), {"id": f"{figure_id}-tick-label-x-{index}", "class": "tick-label", "x": fmt(x_value), "y": fmt(plot_bottom + tick_length + style_values["tickLabelSize"]), "text-anchor": "middle"})
    for index, value in enumerate(axis_ticks(model["y"])):
        y_value = scaled(value, model["y"], plot_bottom, plot_top)
        ET.SubElement(ticks_y, svg_tag("line"), {"id": f"{figure_id}-tick-y-{index}", "class": "axis-line", "x1": fmt(plot_left), "y1": fmt(y_value), "x2": fmt(plot_left - tick_length), "y2": fmt(y_value)})
        add_text(ticks_y, fmt(value), {"id": f"{figure_id}-tick-label-y-{index}", "class": "tick-label", "x": fmt(plot_left - tick_length - style_values["tickLabelSize"] * 0.45), "y": fmt(y_value + style_values["tickLabelSize"] * 0.35), "text-anchor": "end"})
    add_text(root, axis_text(model["x"]), {"id": f"{figure_id}-axis-title-x", "data-role": "axis-title-x", "class": "axis-label", "x": fmt((plot_left + plot_right) / 2), "y": fmt(canvas_h - style_values["axisLabelSize"] * 0.35), "text-anchor": "middle"})
    y_title_x = max(style_values["axisLabelSize"] * 0.65, 2.0)
    add_text(root, axis_text(model["y"]), {"id": f"{figure_id}-axis-title-y", "data-role": "axis-title-y", "class": "axis-label", "x": fmt(y_title_x), "y": fmt((plot_top + plot_bottom) / 2), "text-anchor": "middle", "transform": f"rotate(-90 {fmt(y_title_x)} {fmt((plot_top + plot_bottom) / 2)})"})

    if model.get("series"):
        legend = ET.SubElement(root, svg_tag("g"), {"id": f"{figure_id}-legend", "data-role": "legend"})
        legend_width = min((plot_right - plot_left) * 0.45, style_values["tickLabelSize"] * 12)
        legend_x, legend_y = plot_right - legend_width, plot_top + style_values["tickLabelSize"]
        for index, series in enumerate(model["series"]):
            y_value = legend_y + index * style_values["tickLabelSize"] * 1.25
            color = str(series.get("color", COLORS[index % len(COLORS)]))
            swatch = style_values["tickLabelSize"] * 1.5
            ET.SubElement(legend, svg_tag("line"), {"x1": fmt(legend_x), "y1": fmt(y_value), "x2": fmt(legend_x + swatch), "y2": fmt(y_value), "stroke": color, "stroke-width": str(style_values["dataLineWidth"])})
            add_text(legend, str(series.get("label") or series["id"]), {"class": "tick-label", "x": fmt(legend_x + swatch + style_values["tickLabelSize"] * 0.4), "y": fmt(y_value + style_values["tickLabelSize"] * 0.35)})

    annotations = ET.SubElement(root, svg_tag("g"), {"id": f"{figure_id}-annotations", "data-role": "annotations"})
    for index, annotation in enumerate(model.get("annotations", [])):
        if not isinstance(annotation, dict) or "x" not in annotation or "y" not in annotation or "text" not in annotation:
            raise ModelError(f"annotation[{index}] requires x, y, and text")
        x_value = scaled(float(annotation["x"]), model["x"], plot_left, plot_right)
        y_value = scaled(float(annotation["y"]), model["y"], plot_bottom, plot_top)
        add_text(annotations, str(annotation["text"]), {"id": f"{figure_id}-annotation-{index}", "data-role": "annotation", "class": "annotation", "x": fmt(x_value), "y": fmt(y_value)})
    return root


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        model = json.loads(args.model.read_text(encoding="utf-8"))
        root = render(model)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ModelError) as exc:
        print(f"Semantic SVG generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Generated standard semantic SVG: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
