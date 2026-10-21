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


def _physical_point(layout, transform, point):
    """Transform an integer-DBU point without an intermediate integer snap."""
    transformed = transform.to_vtrans().trans(kdb.DPoint(point.x, point.y))
    return (transformed.x * layout.dbu, transformed.y * layout.dbu)


def _mask_shapes(layout, top_name, pair):
    """Yield supported mask shapes with their complete recursive transforms."""
    cell = layout.cell(top_name)
    if cell is None:
        raise ValueError(f"missing top cell: {top_name}")
    index = layout.find_layer(*pair)
    if index is None:
        return
    iterator = cell.begin_shapes_rec(index)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_text():
            raise ValueError("TEXT has no mask area; polygonize text before comparison")
        if not (shape.is_polygon() or shape.is_box() or shape.is_path()):
            raise ValueError("unsupported non-mask shape in protected comparison")
        yield shape, iterator.trans()
        iterator.next()


def _physical_polygon_rings(layout, shape, transform):
    polygon = shape.polygon
    rings = [[_physical_point(layout, transform, point) for point in polygon.each_point_hull()]]
    for hole in range(polygon.holes()):
        rings.append([_physical_point(layout, transform, point) for point in polygon.each_point_hole(hole)])
    return rings


def _physical_union(layout, top_name, pair):
    try:
        from shapely.geometry import GeometryCollection, Polygon
        from shapely.ops import unary_union
    except ImportError as exc:
        raise RuntimeError("physical DBU-independent comparison requires Shapely") from exc
    polygons = []
    for shape, transform in _mask_shapes(layout, top_name, pair):
        rings = _physical_polygon_rings(layout, shape, transform)
        if rings[0]:
            polygons.append(Polygon(rings[0], rings[1:]))
    return unary_union(polygons) if polygons else GeometryCollection()


def _vertex_records(layout, top_name, pair):
    """Collect transformed vertices while preserving each record's point order."""
    records = []
    for shape, transform in _mask_shapes(layout, top_name, pair):
        if shape.is_path():
            rings = [[_physical_point(layout, transform, point) for point in shape.path.each_point()]]
            kind = "path-centerline"
        else:
            rings = _physical_polygon_rings(layout, shape, transform)
            kind = "polygon"
        records.append({"kind": kind, "rings": rings})
    return records


def _points_close(first, second, tolerance_um):
    if math.dist(first, second) <= tolerance_um:
        return True
    # The default contract is exact in physical coordinates, but decimal DBU
    # and magnification values are represented by binary floats. Allow only a
    # few ULPs of that representation noise; this is not a process tolerance.
    return all(
        abs(left - right) <= 4 * max(math.ulp(left), math.ulp(right))
        for left, right in zip(first, second)
    )


def _geometry_parts(geometry):
    if geometry.is_empty:
        return
    if hasattr(geometry, "geoms") and geometry.geom_type != "Polygon":
        for part in geometry.geoms:
            yield from _geometry_parts(part)
    else:
        yield geometry


def _numeric_area_tolerance(geometry):
    """Bound boolean-area noise independently for each local XOR component.

    A global perimeter bound is unsound: a large distant mask can make a real
    small island look like floating-point noise. Each component gets only the
    ULP scale of its own coordinates and its own boundary length.
    """
    total = 0.0
    components = 0
    all_within_bound = True
    for component in _geometry_parts(geometry):
        if not component.area:
            continue
        coordinates = []
        if hasattr(component, "exterior"):
            coordinates.extend(component.exterior.coords)
            coordinates.extend(point for ring in component.interiors for point in ring.coords)
        elif hasattr(component, "coords"):
            coordinates.extend(component.coords)
        if not coordinates:
            continue
        ulp = max(max(math.ulp(x) for x in point) for point in coordinates)
        bound = 32 * ulp * component.length
        total += bound
        all_within_bound = all_within_bound and component.area <= bound
        components += 1
    return total, components, all_within_bound


def _ring_matches(reference, candidate, tolerance_um, cyclic):
    if len(reference) != len(candidate):
        return False
    if not reference:
        return True
    starts = range(len(candidate)) if cyclic else (0,)
    return any(
        all(_points_close(point, candidate[(index + start) % len(candidate)], tolerance_um)
            for index, point in enumerate(reference))
        for start in starts
    )


def _record_matches(reference, candidate, tolerance_um):
    if reference["kind"] != candidate["kind"] or len(reference["rings"]) != len(candidate["rings"]):
        return False
    cyclic = reference["kind"] == "polygon"
    return all(_ring_matches(left, right, tolerance_um, cyclic)
               for left, right in zip(reference["rings"], candidate["rings"]))


def compare_vertices(reference, candidate, top_name, layer_pairs, tolerance_um=0.0):
    """Compare physical vertices and order after all instance transforms.

    This is separate from geometry XOR: collinear-point removal can preserve a
    solid while violating a protected sampling-point contract. Different DBUs
    are compared in physical micrometres without common-grid rounding. Polygon
    start vertices may rotate cyclically, but point order and orientation are
    preserved. Hierarchy and raw record identity are intentionally not asserted.
    """
    if not math.isfinite(tolerance_um) or tolerance_um < 0:
        raise ValueError("vertex tolerance must be finite and nonnegative")
    checks = []
    for pair in layer_pairs:
        reference_records = _vertex_records(reference, top_name, pair)
        candidate_records = _vertex_records(candidate, top_name, pair)
        unmatched = list(candidate_records)
        matched = 0
        for record in reference_records:
            for index, other in enumerate(unmatched):
                if _record_matches(record, other, tolerance_um):
                    matched += 1
                    unmatched.pop(index)
                    break
        reference_vertices = sum(len(ring) for record in reference_records for ring in record["rings"])
        candidate_vertices = sum(len(ring) for record in candidate_records for ring in record["rings"])
        checks.append({
            "layer": list(pair),
            "equal": matched == len(reference_records) and not unmatched,
            "reference_records": len(reference_records),
            "candidate_records": len(candidate_records),
            "reference_vertices": reference_vertices,
            "candidate_vertices": candidate_vertices,
        })
    return {"ok": all(check["equal"] for check in checks), "layers": checks,
            "tolerance_um": tolerance_um}


def compare_geometry(reference, candidate, top_name, layer_pairs):
    """Physical geometry XOR including nested transforms and differing DBUs.

    Coordinates are converted to floating micrometres through the full complex
    instance transform, avoiding a coarse common integer grid. This check does
    not assert hierarchy, vertex retention or text semantics.
    """
    checks = []
    for pair in layer_pairs:
        reference_geometry = _physical_union(reference, top_name, pair)
        candidate_geometry = _physical_union(candidate, top_name, pair)
        xor = reference_geometry.symmetric_difference(candidate_geometry)
        numeric_tolerance, numeric_components, numeric_noise_only = _numeric_area_tolerance(xor)
        checks.append({
            "layer": list(pair),
            "equal": xor.is_empty or numeric_noise_only,
            "xor_area_um2": xor.area,
            "numeric_area_tolerance_um2": numeric_tolerance,
            "numeric_noise_components": numeric_components,
        })
    return {"ok": all(check["equal"] for check in checks), "layers": checks}


def compare_files(reference_path, candidate_path, top_name, layer_pairs):
    layouts = []
    for path in (reference_path, candidate_path):
        layout = kdb.Layout()
        layout.read(str(Path(path)))
        layouts.append(layout)
    return compare_geometry(*layouts, top_name, layer_pairs)
