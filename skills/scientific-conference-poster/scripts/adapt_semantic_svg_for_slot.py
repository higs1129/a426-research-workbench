#!/usr/bin/env python3
"""Adapt a standard semantic scientific SVG to a poster slot without scaling the whole figure."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
COLORS = ("#000000", "#d90429", "#0067a5", "#169b45")
STYLE_RATIOS = {
    "axisLabelSize": 0.95,
    "tickLabelSize": 0.82,
    "annotationSize": 0.82,
    "dataLineWidth": 0.07,
    "markerDiameter": 0.41,
    "axisLineWidth": 0.06,
    "tickLength": 0.45,
}
MARGIN_RATIOS = {"left": 3.0, "right": 1.0, "top": 1.0, "bottom": 2.4}


class AdaptError(ValueError):
    pass


def tag(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def finite(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AdaptError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise AdaptError(f"{label} must be finite")
    return result


def fmt(value: float) -> str:
    if value == 0:
        return "0"
    return f"{value:.6g}"


def find_role(root: ET.Element, role: str) -> ET.Element:
    for element in root.iter():
        if element.get("data-role") == role:
            return element
    raise AdaptError(f"standard SVG is missing data-role={role}")


def parse_model(root: ET.Element) -> tuple[ET.Element, dict]:
    metadata = find_role(root, "figure-model")
    try:
        model = json.loads(metadata.text or "")
    except json.JSONDecodeError as exc:
        raise AdaptError(f"figure-model metadata is invalid: {exc}") from exc
    if not isinstance(model, dict):
        raise AdaptError("figure-model must be an object")
    return metadata, model


def axis_ticks(axis: dict) -> list[float]:
    if isinstance(axis.get("ticks"), list) and axis["ticks"]:
        return [finite(value, "tick") for value in axis["ticks"]]
    start, end = map(float, axis["domain"])
    if axis.get("scale", "linear") == "log":
        low, high = sorted((math.floor(math.log10(start)), math.ceil(math.log10(end))))
        values = [10.0**power for power in range(low, high + 1) if min(start, end) <= 10.0**power <= max(start, end)]
        return values if start < end else list(reversed(values))
    low, high = sorted((start, end))
    rough = (high - low) / 5
    exponent = math.floor(math.log10(rough))
    fraction = rough / (10**exponent)
    step = next(value for value in (1, 2, 2.5, 5, 10) if fraction <= value) * (10**exponent)
    value = math.ceil(low / step - 1e-12) * step
    values = []
    while value <= high + step * 1e-9 and len(values) < 100:
        values.append(round(value, max(0, 10 - exponent)))
        value += step
    return values if start < end else list(reversed(values))


def scaled(value: float, axis: dict, start_pixel: float, end_pixel: float) -> float:
    start, end = map(float, axis["domain"])
    if axis.get("scale", "linear") == "log":
        value, start, end = math.log10(value), math.log10(start), math.log10(end)
    return start_pixel + (value - start) / (end - start) * (end_pixel - start_pixel)


def clear(element: ET.Element) -> None:
    for child in list(element):
        element.remove(child)


def add_text(parent: ET.Element, value: str, attributes: dict[str, str]) -> ET.Element:
    node = ET.SubElement(parent, tag("text"), attributes)
    node.text = value
    return node


def axis_title(axis: dict) -> str:
    title = str(axis.get("title", "")).strip()
    unit = str(axis.get("unit", "")).strip()
    return f"{title} ({unit})" if unit else title


def adapt(root: ET.Element, width_mm: float, height_mm: float, base_mm: float, margins: dict[str, float], style: dict[str, float]) -> ET.Element:
    if root.get("data-role") != "scientific-figure":
        raise AdaptError("input is not a standard semantic scientific SVG")
    if root.get("data-source-origin") not in {"authoritative-data", "inline-data-html", "canvas-reconstruction"}:
        raise AdaptError("input lacks a supported source-origin marker")
    metadata, model = parse_model(root)
    for axis_name in ("x", "y"):
        if not isinstance(model.get(axis_name), dict) or not isinstance(model[axis_name].get("domain"), list):
            raise AdaptError(f"figure model lacks {axis_name} axis semantics")
    figure_id = root.get("id") or str(model.get("figureId") or "figure")
    canvas_w = width_mm
    canvas_h = height_mm
    plot_left, plot_top = margins["left"], margins["top"]
    plot_right, plot_bottom = canvas_w - margins["right"], canvas_h - margins["bottom"]
    if plot_right <= plot_left or plot_bottom <= plot_top:
        raise AdaptError("slot margins leave no positive plot area")

    root.set("width", f"{width_mm:g}mm")
    root.set("height", f"{height_mm:g}mm")
    root.set("viewBox", f"0 0 {width_mm:g} {height_mm:g}")
    root.set("preserveAspectRatio", "xMidYMid meet")
    root.set("data-user-unit-mm", "1")
    root.set("data-physical-coordinate-system", "mm-isomorphic")
    root.set("data-poster-base-mm", f"{base_mm:g}")
    root.set("data-poster-slot-width-mm", f"{width_mm:g}")
    root.set("data-poster-slot-height-mm", f"{height_mm:g}")
    root.set("data-poster-adaptation", "semantic-reflow")

    plot_box = find_role(root, "plot-box")
    plot_box.attrib.update({"x": fmt(plot_left), "y": fmt(plot_top), "width": fmt(plot_right - plot_left), "height": fmt(plot_bottom - plot_top)})
    for clip in root.iter(tag("clipPath")):
        rectangle = next((child for child in list(clip) if local_name(child.tag) == "rect"), None)
        if rectangle is not None:
            rectangle.attrib.update({"x": fmt(plot_left), "y": fmt(plot_top), "width": fmt(plot_right - plot_left), "height": fmt(plot_bottom - plot_top)})

    model_series = {str(item.get("id")): item for item in model.get("series", []) if isinstance(item, dict)}
    for group in [element for element in root.iter() if element.get("data-role") == "data-series"]:
        series_id = group.get("data-series-id", "")
        series = model_series.get(series_id)
        if not series or not isinstance(series.get("points"), list):
            raise AdaptError(f"figure model lacks points for series {series_id}")
        clear(group)
        coordinates = [(scaled(float(point[0]), model["x"], plot_left, plot_right), scaled(float(point[1]), model["y"], plot_bottom, plot_top)) for point in series["points"]]
        kind = str(series.get("kind", "polyline"))
        group.set("data-series-kind", kind)
        if kind in {"polyline", "point-line"}:
            ET.SubElement(group, tag("polyline"), {"id": f"{figure_id}-{series_id}-path", "points": " ".join(f"{fmt(x)},{fmt(y)}" for x, y in coordinates)})
        if kind in {"scatter", "point-line"}:
            default_radius = style["markerDiameter"] / 2
            for index, (x_value, y_value) in enumerate(coordinates):
                attributes = {"id": f"{figure_id}-{series_id}-point-{index}", "class": "data-marker", "data-role": "data-marker", "cx": fmt(x_value), "cy": fmt(y_value), "r": fmt(float(series.get("markerRadius", default_radius)))}
                if "markerRadius" not in series:
                    attributes["data-default-size"] = "true"
                ET.SubElement(group, tag("circle"), attributes)

    # Physical stroke widths must follow the millimetre-calibrated coordinate
    # system; non-scaling-stroke would break that mapping.
    for element in root.iter():
        if element.get("vector-effect") == "non-scaling-stroke":
            element.attrib.pop("vector-effect", None)

    field = next((element for element in root.iter() if element.get("data-role") == "raster-field"), None)
    if field is not None:
        field.attrib.update({"x": fmt(plot_left), "y": fmt(plot_top), "width": fmt(plot_right - plot_left), "height": fmt(plot_bottom - plot_top), "preserveAspectRatio": "none"})
        pixel_w = finite(field.get("data-pixel-width"), "raster pixel width")
        pixel_h = finite(field.get("data-pixel-height"), "raster pixel height")
        physical_w = plot_right - plot_left
        physical_h = plot_bottom - plot_top
        field.set("data-effective-dpi", f"{min(pixel_w / (physical_w / 25.4), pixel_h / (physical_h / 25.4)):.2f}")

    tick_length = style["tickLength"]
    ticks_x, ticks_y = find_role(root, "ticks-x"), find_role(root, "ticks-y")
    clear(ticks_x)
    clear(ticks_y)
    for index, value in enumerate(axis_ticks(model["x"])):
        x_value = scaled(value, model["x"], plot_left, plot_right)
        ET.SubElement(ticks_x, tag("line"), {"id": f"{figure_id}-tick-x-{index}", "class": "axis-line", "x1": fmt(x_value), "y1": fmt(plot_bottom), "x2": fmt(x_value), "y2": fmt(plot_bottom + tick_length)})
        add_text(ticks_x, fmt(value), {"id": f"{figure_id}-tick-label-x-{index}", "class": "tick-label", "x": fmt(x_value), "y": fmt(plot_bottom + tick_length + style["tickLabelSize"]), "text-anchor": "middle"})
    for index, value in enumerate(axis_ticks(model["y"])):
        y_value = scaled(value, model["y"], plot_bottom, plot_top)
        ET.SubElement(ticks_y, tag("line"), {"id": f"{figure_id}-tick-y-{index}", "class": "axis-line", "x1": fmt(plot_left), "y1": fmt(y_value), "x2": fmt(plot_left - tick_length), "y2": fmt(y_value)})
        add_text(ticks_y, fmt(value), {"id": f"{figure_id}-tick-label-y-{index}", "class": "tick-label", "x": fmt(plot_left - tick_length - style["tickLabelSize"] * 0.45), "y": fmt(y_value + style["tickLabelSize"] * 0.35), "text-anchor": "end"})

    title_x, title_y = find_role(root, "axis-title-x"), find_role(root, "axis-title-y")
    title_x.text = axis_title(model["x"])
    title_x.attrib.update({"x": fmt((plot_left + plot_right) / 2), "y": fmt(canvas_h - style["axisLabelSize"] * 0.35), "text-anchor": "middle"})
    center_y = (plot_top + plot_bottom) / 2
    title_y.text = axis_title(model["y"])
    y_title_x = max(style["axisLabelSize"] * 0.65, 2.0)
    title_y.attrib.update({"x": fmt(y_title_x), "y": fmt(center_y), "text-anchor": "middle", "transform": f"rotate(-90 {fmt(y_title_x)} {fmt(center_y)})"})

    legends = [element for element in root.iter() if element.get("data-role") == "legend"]
    if legends:
        legend = legends[0]
        clear(legend)
        legend_width = min((plot_right - plot_left) * 0.45, style["tickLabelSize"] * 12)
        start_x, start_y = plot_right - legend_width, plot_top + style["tickLabelSize"]
        for index, series in enumerate(model.get("series", [])):
            y_value = start_y + index * style["tickLabelSize"] * 1.25
            color = str(series.get("color", COLORS[index % len(COLORS)]))
            swatch = style["tickLabelSize"] * 1.5
            ET.SubElement(legend, tag("line"), {"x1": fmt(start_x), "y1": fmt(y_value), "x2": fmt(start_x + swatch), "y2": fmt(y_value), "stroke": color, "stroke-width": fmt(style["dataLineWidth"])})
            add_text(legend, str(series.get("label") or series.get("id")), {"class": "tick-label", "x": fmt(start_x + swatch + style["tickLabelSize"] * 0.4), "y": fmt(y_value + style["tickLabelSize"] * 0.35)})

    annotations = find_role(root, "annotations")
    clear(annotations)
    for index, annotation in enumerate(model.get("annotations", [])):
        if not isinstance(annotation, dict) or not all(key in annotation for key in ("x", "y", "text")):
            raise AdaptError(f"annotation {index} is incomplete")
        add_text(annotations, str(annotation["text"]), {"id": f"{figure_id}-annotation-{index}", "data-role": "annotation", "class": "annotation", "x": fmt(scaled(float(annotation["x"]), model["x"], plot_left, plot_right)), "y": fmt(scaled(float(annotation["y"]), model["y"], plot_bottom, plot_top))})

    for parent in root.iter():
        for child in list(parent):
            if child.get("data-role") == "poster-slot-style":
                parent.remove(child)
    override = ET.SubElement(root, tag("style"), {"data-role": "poster-slot-style"})
    override.text = "svg[data-role='scientific-figure']{" + ";".join((f"--axis-label-size:{style['axisLabelSize']}px", f"--tick-label-size:{style['tickLabelSize']}px", f"--annotation-size:{style['annotationSize']}px", f"--data-line-width:{style['dataLineWidth']}px", f"--marker-diameter:{style['markerDiameter']}px", f"--axis-line-width:{style['axisLineWidth']}px", f"--tick-length:{style['tickLength']}px")) + "}"
    model["posterAdaptation"] = {"coordinateSystem": {"unit": "mm", "mmPerUserUnit": 1}, "slotWidthMm": width_mm, "slotHeightMm": height_mm, "baseMm": base_mm, "margins": margins, "style": style}
    metadata.text = json.dumps(model, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return root


def parse_mapping(value: str, defaults: dict[str, float], label: str) -> dict[str, float]:
    result = dict(defaults)
    if not value:
        return result
    for item in value.split(","):
        if "=" not in item:
            raise AdaptError(f"{label} entries must use key=value")
        key, raw = (part.strip() for part in item.split("=", 1))
        if key not in result:
            raise AdaptError(f"unsupported {label} key: {key}")
        result[key] = finite(raw, f"{label}.{key}")
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width-mm", type=float, required=True)
    parser.add_argument("--height-mm", type=float, required=True)
    parser.add_argument("--base-mm", type=float, default=10.0, help="poster body-type baseline B in millimetres (default: 10)")
    parser.add_argument("--margins", default="", help="optional millimetre overrides: left=...,right=...,top=...,bottom=...")
    parser.add_argument("--style", default="", help="optional millimetre overrides: axisLabelSize=...,tickLabelSize=...,annotationSize=...,dataLineWidth=...,markerDiameter=...,axisLineWidth=...,tickLength=...")
    args = parser.parse_args()
    try:
        if args.width_mm <= 0 or args.height_mm <= 0 or args.base_mm <= 0:
            raise AdaptError("slot dimensions and base-mm must be positive")
        root = ET.parse(args.input).getroot()
        margins = parse_mapping(args.margins, {key: ratio * args.base_mm for key, ratio in MARGIN_RATIOS.items()}, "margins")
        style = parse_mapping(args.style, {key: ratio * args.base_mm for key, ratio in STYLE_RATIOS.items()}, "style")
        adapted = adapt(root, args.width_mm, args.height_mm, args.base_mm, margins, style)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(ET.tostring(adapted, encoding="unicode") + "\n", encoding="utf-8")
    except (OSError, ET.ParseError, AdaptError, ValueError) as exc:
        print(f"Poster-slot adaptation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Adapted semantic SVG for poster slot: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
