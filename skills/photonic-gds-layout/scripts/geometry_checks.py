"""Small geometry invariants; inputs are explicit, no process constants are hidden."""
from __future__ import annotations

import math
from pathlib import Path

import klayout.db as kdb


def check_dbu_extent(dbu_um, extent_um, integer_limit=2**31 - 1):
    """Check both absolute coordinates and span BEFORE converting to integer DBU."""
    if not math.isfinite(dbu_um) or dbu_um <= 0:
        raise ValueError("DBU must be finite and positive")
    if len(extent_um) != 4 or not all(math.isfinite(v) for v in extent_um):
        raise ValueError("extent must be finite [left, bottom, right, top]")
    left, bottom, right, top = extent_um
    if left > right or bottom > top:
        raise ValueError("extent is reversed")
    # ceil reserves a DBU for rounding; a downstream limit may be stricter.
    absolute = math.ceil(max(abs(v) for v in extent_um) / dbu_um)
    span = math.ceil(max(right - left, top - bottom) / dbu_um)
    if max(absolute, span) >= integer_limit:
        raise ValueError("DBU overflows absolute coordinate or full span; choose coarser DBU or explicit origin")
    return {"max_absolute_dbu": absolute, "max_span_dbu": span, "integer_limit": integer_limit}


def shared_station_strip(centerline, normals, width_um, max_stations=2000):
    """Fragment a curve with the SAME station indices on both offset boundaries.

    Normals must be unit vectors, widths positive, and offset-fold validity is
    the caller's responsibility. Boundaries share exact end cross sections.
    Straight/rectangular segments need only their actual endpoints.
    """
    if len(centerline) < 2 or len(centerline) != len(normals) or max_stations < 2:
        raise ValueError("matching stations/normals and max_stations >= 2 required")
    widths = [width_um] * len(centerline) if isinstance(width_um, (int, float)) else list(width_um)
    if len(widths) != len(centerline):
        raise ValueError("one width per station required")
    inner, outer = [], []
    previous = None
    for point, normal, width in zip(centerline, normals, widths):
        if len(point) != 2 or len(normal) != 2 or not all(math.isfinite(v) for v in (*point, *normal, width)):
            raise ValueError("finite 2D stations/normals and widths required")
        if width <= 0 or not math.isclose(math.hypot(*normal), 1.0, abs_tol=1e-9):
            raise ValueError("positive width and unit normal required")
        if previous is not None and math.dist(point, previous) == 0:
            raise ValueError("repeated adjacent centerline station")
        previous = point
        inner.append((point[0] - normal[0] * width / 2, point[1] - normal[1] * width / 2))
        outer.append((point[0] + normal[0] * width / 2, point[1] + normal[1] * width / 2))
    polygons = []
    for start in range(0, len(centerline) - 1, max_stations - 1):
        stop = min(start + max_stations, len(centerline))
        polygons.append(outer[start:stop] + list(reversed(inner[start:stop])))
    return polygons


def check_curve_fragment(points, width_um, max_boundary_step_um, tolerance_um):
    """Check a shared-station polygon's two caps, widths and curve edges.

    This is a pre-fracturing contract for paired-boundary polygons. It does not
    classify arbitrary imported polygons or prove global curvature/clearance.
    """
    if len(points) < 4 or len(points) % 2:
        raise ValueError("paired-boundary curve polygon required")
    if not all(math.isfinite(v) and v >= 0 for v in (width_um, max_boundary_step_um, tolerance_um)) or width_um == 0 or max_boundary_step_um == 0:
        raise ValueError("positive width/step and nonnegative tolerance required")
    count = len(points) // 2
    outer, inner = points[:count], list(reversed(points[count:]))
    widths = [math.dist(a, b) for a, b in zip(outer, inner)]
    steps = [math.dist(a, b) for boundary in (outer, inner) for a, b in zip(boundary, boundary[1:])]
    if max(abs(w - width_um) for w in widths) > tolerance_um:
        raise ValueError("curve fragment width/caps mismatch: boundaries must share station indices")
    if max(steps) > max_boundary_step_um + tolerance_um:
        raise ValueError("abnormally long curve boundary chord")
    return {"min_width_um": min(widths), "max_width_um": max(widths), "max_boundary_step_um": max(steps)}


def check_ports(first, second, tolerance_um=0.0, angle_tolerance_deg=0.0):
    """Direct ports face opposite directions. Tapers expose their own ports."""
    if not all(math.isfinite(v) and v >= 0 for v in (tolerance_um, angle_tolerance_deg)):
        raise ValueError("nonnegative port tolerances required")
    for port in (first, second):
        if len(port["center_um"]) != 2 or not all(math.isfinite(v) for v in (*port["center_um"], port["width_um"], port["orientation_deg"])) or port["width_um"] <= 0:
            raise ValueError("finite port position/direction and positive width required")
    if tuple(first["layer"]) != tuple(second["layer"]):
        raise ValueError("port layer mismatch")
    if math.dist(first["center_um"], second["center_um"]) > tolerance_um:
        raise ValueError("port position mismatch")
    if abs(first["width_um"] - second["width_um"]) > tolerance_um:
        raise ValueError("port width mismatch; an explicit taper is required")
    delta = (first["orientation_deg"] - second["orientation_deg"]) % 360
    if abs(delta - 180) > angle_tolerance_deg:
        raise ValueError("port direction mismatch")


def check_required_corridors(actual_region, required_corridors):
    """DBU Regions: every intended joint/lead corridor must be covered at full width."""
    missing = required_corridors - actual_region
    if not missing.is_empty():
        raise ValueError("joint/lead has a gap or unintended neck inside required full-width corridor")


def layer_region(layout, top_name, pair):
    cell = layout.cell(top_name)
    if cell is None:
        raise ValueError(f"missing top cell: {top_name}")
    index = layout.find_layer(*pair)
    if index is None:
        return kdb.Region()
    return kdb.Region(cell.begin_shapes_rec(index))


def compare_geometry(reference, candidate, top_name, layer_pairs):
    """Physical geometry XOR, including instance transforms; equal DBU required.

    PATHs are expanded by Region; TEXT is not mask geometry. Preflight must
    handle TEXT separately. This check does not assert equal hierarchy.
    """
    if not math.isclose(reference.dbu, candidate.dbu, rel_tol=0, abs_tol=1e-15):
        raise ValueError("DBUs differ; explicitly quantize a comparison copy before XOR")
    checks = []
    for pair in layer_pairs:
        for layout in (reference, candidate):
            cell = layout.cell(top_name)
            index = layout.find_layer(*pair)
            if cell is not None and index is not None:
                iterator = cell.begin_shapes_rec(index)
                while not iterator.at_end():
                    if iterator.shape().is_text():
                        raise ValueError("TEXT has no mask area; polygonize text before geometry XOR")
                    iterator.next()
        xor = layer_region(reference, top_name, pair) ^ layer_region(candidate, top_name, pair)
        checks.append({"layer": list(pair), "equal": xor.is_empty(), "xor_area_um2": xor.area() * reference.dbu**2})
    return {"ok": all(check["equal"] for check in checks), "layers": checks}


def compare_files(reference_path, candidate_path, top_name, layer_pairs):
    layouts = []
    for path in (reference_path, candidate_path):
        layout = kdb.Layout()
        layout.read(str(Path(path)))
        layouts.append(layout)
    return compare_geometry(*layouts, top_name, layer_pairs)
