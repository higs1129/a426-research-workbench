#!/usr/bin/env python3
"""Generate and verify the reference microring with Euler edge transitions."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import klayout.db as kdb

from validate_design_spec import load_spec, validate_spec
from geometry_checks import check_dbu_extent, compare_geometry, shared_station_strip


Point = tuple[float, float]


def _append_straight(points: list[Point], heading: float, length: float) -> float:
    x, y = points[-1]
    points.append((x + length * math.cos(heading), y + length * math.sin(heading)))
    return heading


def _append_euler(
    points: list[Point], heading: float, angle_deg: float, min_radius_um: float, samples: int
) -> float:
    """Append a pure symmetric clothoid bend with triangular curvature."""
    sign = 1.0 if angle_deg >= 0 else -1.0
    angle = abs(math.radians(angle_deg))
    half_length = angle * min_radius_um
    total_length = 2.0 * half_length
    ds = total_length / samples
    x, y = points[-1]
    theta = heading
    for index in range(samples):
        midpoint_s = (index + 0.5) * ds
        if midpoint_s <= half_length:
            curvature = midpoint_s / (min_radius_um * half_length)
        else:
            curvature = (total_length - midpoint_s) / (min_radius_um * half_length)
        dtheta = sign * curvature * ds
        x += ds * math.cos(theta + dtheta / 2.0)
        y += ds * math.sin(theta + dtheta / 2.0)
        theta += dtheta
        points.append((x, y))
    return heading + math.radians(angle_deg)


def build_route(spec: dict[str, Any], report: dict[str, Any]) -> tuple[list[Point], dict[str, Any]]:
    waveguide = spec["waveguide"]
    radius = report["waveguide"]["euler_min_radius_um"]
    samples = report["waveguide"]["points_per_90_deg"]
    coupling_length = report["waveguide"]["coupling_length_um"]
    left = waveguide["left_edge"]
    right = waveguide["right_edge"]

    points: list[Point] = [(0.0, 0.0)]
    heading = 0.0
    heading = _append_straight(points, heading, float(left["straight_length_um"]))
    heading = _append_euler(points, heading, 90.0, radius, samples)
    heading = _append_straight(points, heading, float(left["vertical_drop_um"]))
    heading = _append_euler(points, heading, -90.0, radius, samples)
    bus_start = points[-1]
    heading = _append_straight(points, heading, coupling_length)
    bus_end = points[-1]
    heading = _append_euler(points, heading, -90.0, radius, samples)
    heading = _append_straight(points, heading, float(right["vertical_drop_um"]))
    heading = _append_euler(points, heading, 90.0, radius, samples)
    _append_straight(points, heading, float(right["straight_length_um"]))

    ring = report["ring"]
    bus_y = (
        ring["radius_um"]
        + ring["width_um"] / 2.0
        + report["waveguide"]["coupling_gap_um"]
        + report["waveguide"]["width_um"] / 2.0
    )
    dx = -(bus_start[0] + bus_end[0]) / 2.0
    dy = bus_y - bus_start[1]
    translated = [(x + dx, y + dy) for x, y in points]
    bus_start = (bus_start[0] + dx, bus_start[1] + dy)
    bus_end = (bus_end[0] + dx, bus_end[1] + dy)
    return translated, {
        "bus_start_um": list(bus_start),
        "bus_end_um": list(bus_end),
        "bus_center_y_um": bus_y,
        "input_port_um": list(translated[0]),
        "output_port_um": list(translated[-1]),
        "centerline_points": len(translated),
        "end_heading_deg": math.degrees(heading),
    }


def build_ring(radius_um: float, segments: int) -> list[Point]:
    return [
        (
            radius_um * math.cos(2.0 * math.pi * index / segments),
            radius_um * math.sin(2.0 * math.pi * index / segments),
        )
        for index in range(segments + 1)
    ]


def split_closed_path(points: list[Point], parts: int = 4) -> list[list[Point]]:
    """Split a closed sampled path without losing or duplicating logical vertices."""
    segments = len(points) - 1
    base, remainder = divmod(segments, parts)
    result: list[list[Point]] = []
    start = 0
    for part_index in range(parts):
        count = base + (1 if part_index < remainder else 0)
        end = start + count
        result.append(points[start : end + 1])
        start = end
    return result


def _point_to_line_distance(point: Point, start: Point, end: Point) -> float:
    vx, vy = end[0] - start[0], end[1] - start[1]
    wx, wy = point[0] - start[0], point[1] - start[1]
    denominator = math.hypot(vx, vy)
    return abs(vx * wy - vy * wx) / denominator


def _readback_paths(gds_path: Path, top_cell: str, device_layer: list[int]) -> tuple[kdb.Layout, list[dict[str, Any]]]:
    layout = kdb.Layout()
    layout.read(str(gds_path))
    cell = layout.cell(top_cell)
    if cell is None:
        raise RuntimeError(f"Top cell '{top_cell}' was not found after GDS read-back.")
    layer_index = layout.layer(kdb.LayerInfo(device_layer[0], device_layer[1]))
    paths: list[dict[str, Any]] = []
    for shape in cell.shapes(layer_index).each():
        if not shape.is_path():
            continue
        path = shape.path
        points = [(point.x * layout.dbu, point.y * layout.dbu) for point in path.each_point()]
        paths.append({"points": points, "width_um": path.width * layout.dbu})
    return layout, paths


def verify_path_readback(
    gds_path: Path, spec: dict[str, Any], validation: dict[str, Any], route_info: dict[str, Any]
) -> dict[str, Any]:
    layout, paths = _readback_paths(gds_path, validation["top_cell"], spec["layers"]["device"])
    if len(paths) != 5:
        raise RuntimeError(f"Expected four ring paths and one route path, found {len(paths)} total paths.")
    route_candidates = [item for item in paths if len(item["points"]) == route_info["centerline_points"]]
    if len(route_candidates) != 1:
        raise RuntimeError("Could not uniquely identify the continuous edge-to-edge route after read-back.")
    route_path = route_candidates[0]
    ring_paths = [item for item in paths if item is not route_path]
    ring_widths = [item["width_um"] for item in ring_paths]
    unique_ring_points = {
        (x, y)
        for item in ring_paths
        for x, y in item["points"]
    }
    ring_points = sorted(unique_ring_points, key=lambda point: math.atan2(point[1], point[0]))
    deviations_nm = []
    for index, point in enumerate(ring_points):
        start = ring_points[(index - 1) % len(ring_points)]
        end = ring_points[(index + 1) % len(ring_points)]
        deviations_nm.append(_point_to_line_distance(point, start, end) * 1000.0)

    expected = validation["ring"]
    tolerance_nm = math.sqrt(2) * layout.dbu * 1000.0
    mean_deviation = sum(deviations_nm) / len(deviations_nm)
    checks = {
        "top_cell_present": True,
        "device_path_count_is_five": len(paths) == 5,
        "ring_is_four_quadrant_paths": len(ring_paths) == 4,
        "ring_segment_count_matches": len(ring_points) == expected["segments"],
        "ring_width_matches": all(abs(width - expected["width_um"]) <= layout.dbu for width in ring_widths),
        "route_width_matches": abs(route_path["width_um"] - validation["waveguide"]["width_um"]) <= layout.dbu,
        "ring_deviation_within_bound": max(deviations_nm) < expected["target_midpoint_chord_deviation_nm"],
        "route_is_continuous_single_path": len(route_path["points"]) == route_info["centerline_points"],
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "readback": {
            "dbu_um": layout.dbu,
            "ring_segments": len(ring_points),
            "ring_path_count": len(ring_paths),
            "ring_width_um": sum(ring_widths) / len(ring_widths),
            "route_width_um": route_path["width_um"],
            "ring_midpoint_chord_deviation_nm": {
                "target": expected["target_midpoint_chord_deviation_nm"],
                "mean": mean_deviation,
                "minimum": min(deviations_nm),
                "maximum": max(deviations_nm),
                "tolerance_used": tolerance_nm,
            },
            "route_centerline_points": len(route_path["points"]),
        },
    }


def verify_polygon_readback(
    gds_path: Path, spec: dict[str, Any], validation: dict[str, Any], route_info: dict[str, Any]
) -> dict[str, Any]:
    layout = kdb.Layout()
    layout.read(str(gds_path))
    cell = layout.cell(validation["top_cell"])
    if cell is None:
        raise RuntimeError(f"Top cell '{validation['top_cell']}' was not found after GDS read-back.")
    device_layer = spec["layers"]["device"]
    layer_index = layout.layer(kdb.LayerInfo(device_layer[0], device_layer[1]))
    shapes = list(cell.shapes(layer_index).each())
    polygons = [shape.polygon for shape in shapes if shape.is_polygon()]
    paths = [shape for shape in shapes if shape.is_path()]
    route_candidates = [
        polygon
        for polygon in polygons
        if polygon.bbox().width() * layout.dbu > 2.0 * validation["ring"]["outer_radius_um"]
    ]
    positive_areas = [polygon.area() * layout.dbu**2 for polygon in polygons]
    ring_polygons = [polygon for polygon in polygons if polygon not in route_candidates]
    # Collect saved inner/outer stations independent of vertex start/order.
    # Reject a mean-only check: one malformed chord must fail the upper bound.
    radii = (validation["ring"]["inner_radius_um"], validation["ring"]["outer_radius_um"])
    boundary_reports = []
    radial_tolerance = math.sqrt(2) * layout.dbu
    for radius in radii:
        points = {(p.x * layout.dbu, p.y * layout.dbu) for poly in ring_polygons
                  for p in poly.each_point_hull()
                  if abs(math.hypot(p.x * layout.dbu, p.y * layout.dbu) - radius) <= radial_tolerance}
        points = sorted(points, key=lambda p: math.atan2(p[1], p[0]))
        deviations = [_point_to_line_distance(p, points[i-1], points[(i+1) % len(points)]) * 1000
                      for i, p in enumerate(points)] if len(points) >= 3 else [math.inf]
        steps = [math.dist(p, points[i-1]) for i, p in enumerate(points)]
        allowed_step = 2 * radius * math.sin(math.pi / validation["ring"]["segments"]) + 2 * radial_tolerance
        boundary_reports.append({"radius_um": radius, "points": len(points),
                                 "max_deviation_nm": max(deviations),
                                 "max_step_um": max(steps, default=math.inf),
                                 "allowed_step_um": allowed_step})
    checks = {
        "top_cell_present": True,
        "device_shape_count_is_five": len(shapes) == 5,
        "device_path_count_is_zero": len(paths) == 0,
        "device_polygon_count_is_five": len(polygons) == 5,
        "all_polygon_areas_are_positive": len(positive_areas) == 5 and all(area > 0 for area in positive_areas),
        "route_is_single_polygon": len(route_candidates) == 1,
        "ring_boundaries_station_count_matches": all(b["points"] == validation["ring"]["segments"] for b in boundary_reports),
        "ring_boundaries_deviation_within_bound": all(b["max_deviation_nm"] < validation["ring"]["target_midpoint_chord_deviation_nm"] for b in boundary_reports),
        "ring_boundaries_no_long_chords": all(b["max_step_um"] <= b["allowed_step_um"] for b in boundary_reports),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "readback": {
            "dbu_um": layout.dbu,
            "shape_representation": "polygon",
            "device_shape_count": len(shapes),
            "device_path_count": len(paths),
            "device_polygon_count": len(polygons),
            "polygon_areas_um2": positive_areas,
            "route_centerline_points_before_expansion": route_info["centerline_points"],
            "ring_boundaries": boundary_reports,
        },
    }
def render_preview(ring_points: list[Point], route_points: list[Point], output: Path, validation: dict[str, Any]) -> None:
    import matplotlib.pyplot as plt

    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 7), dpi=180)
    rx, ry = zip(*ring_points)
    wx, wy = zip(*route_points)
    ring = validation["ring"]
    ax.plot(rx, ry, color="#d97706", linewidth=3.0,
            label=f"Microring R={ring['radius_um']:g} µm, W={ring['width_um']:g} µm")
    ax.plot(wx, wy, color="#087f8c", linewidth=3.0, label="Straight bus + Euler edge transitions")
    ax.scatter([wx[0], wx[-1]], [wy[0], wy[-1]], color="#1f2937", s=22, zorder=4)
    ax.annotate("opt_in", (wx[0], wy[0]), xytext=(8, 8), textcoords="offset points")
    ax.annotate("opt_out", (wx[-1], wy[-1]), xytext=(-48, 8), textcoords="offset points")
    ax.axhline(validation["ring"]["outer_radius_um"], color="#9ca3af", linewidth=0.7, linestyle=":")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, color="#e5e7eb", linewidth=0.6)
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    ax.set_title("Reference microring and Euler route")
    ax.legend(loc="lower center", ncol=2)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def generate(
    spec_path: Path,
    output_gds: Path,
    report_path: Path,
    preview_path: Path | None = None,
    shape_representation: str = "polygon",
) -> dict[str, Any]:
    if shape_representation not in {"path", "polygon"}:
        raise ValueError("shape_representation must be 'path' or 'polygon'.")
    spec = load_spec(spec_path)
    validation = validate_spec(spec)
    route_points, route_info = build_route(spec, validation)
    ring_points = build_ring(validation["ring"]["radius_um"], validation["ring"]["segments"])

    all_points = ring_points + route_points
    margin = max(validation["ring"]["width_um"], validation["waveguide"]["width_um"]) / 2
    extent = [min(p[0] for p in all_points) - margin, min(p[1] for p in all_points) - margin,
              max(p[0] for p in all_points) + margin, max(p[1] for p in all_points) + margin]
    integer_check = check_dbu_extent(validation["dbu_um"], extent)

    layout = kdb.Layout()
    layout.dbu = validation["dbu_um"]
    cell = layout.create_cell(validation["top_cell"])
    device = spec["layers"]["device"]
    layer_index = layout.layer(kdb.LayerInfo(device[0], device[1]))
    if shape_representation == "path":
        for ring_part in split_closed_path(ring_points):
            cell.shapes(layer_index).insert(kdb.DPath(
                [kdb.DPoint(x, y) for x, y in ring_part], validation["ring"]["width_um"]))
    else:
        radius = validation["ring"]["radius_um"]
        normals = [(x / radius, y / radius) for x, y in ring_points]
        # Radial caps share exact stations. Separately polygonized PATH parts
        # have different end tangents and can introduce tiny seam wedges.
        fragments = shared_station_strip(ring_points, normals, validation["ring"]["width_um"],
                                         max_stations=math.ceil(validation["ring"]["segments"] / 4) + 1)
        for points in fragments:
            cell.shapes(layer_index).insert(kdb.DPolygon([kdb.DPoint(*p) for p in points]))
    route_path = kdb.DPath(
        [kdb.DPoint(x, y) for x, y in route_points], validation["waveguide"]["width_um"]
    )
    cell.shapes(layer_index).insert(
        route_path if shape_representation == "path" else route_path.polygon()
    )

    output_gds.parent.mkdir(parents=True, exist_ok=True)
    candidate = output_gds.with_name(output_gds.stem + ".candidate.gds")
    if candidate.exists():
        raise FileExistsError(f"Candidate already exists; inspect before retrying: {candidate}")
    layout.write(str(candidate))
    if shape_representation == "path":
        readback = verify_path_readback(candidate, spec, validation, route_info)
    else:
        readback = verify_polygon_readback(candidate, spec, validation, route_info)
    saved = kdb.Layout()
    saved.read(str(candidate))
    equality = compare_geometry(layout, saved, validation["top_cell"], [device])
    readback["checks"]["saved_geometry_matches_source"] = equality["ok"]
    readback["ok"] = all(readback["checks"].values())
    if readback["ok"]:
        candidate.replace(output_gds)
    report = {
        "ok": readback["ok"],
        "spec": str(spec_path),
        "gds": str(output_gds),
        "shape_representation": shape_representation,
        "validation": validation,
        "route": route_info,
        "verification": readback,
        "integer_range": integer_check,
        "candidate_if_failed": str(candidate) if not readback["ok"] else None,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if preview_path is not None:
        render_preview(ring_points, route_points, preview_path, validation)
        report["preview"] = str(preview_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output-gds", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument(
        "--shape-representation",
        choices=("path", "polygon"),
        default="polygon",
        help="Keep centerlines as GDS PATH elements or expand them into BOUNDARY/POLYGON elements.",
    )
    args = parser.parse_args()
    try:
        report = generate(
            args.spec,
            args.output_gds,
            args.report,
            args.preview,
            args.shape_representation,
        )
    except Exception as exc:  # CLI boundary returns a concise actionable failure.
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
