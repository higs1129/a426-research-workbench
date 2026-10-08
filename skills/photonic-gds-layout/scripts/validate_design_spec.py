#!/usr/bin/env python3
"""Validate a photonic layout YAML specification and derive key geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import yaml

from geometry_checks import check_dbu_extent
from process_rules import resolve_process_defaults


class SpecError(ValueError):
    """Raised when a design specification is incomplete or inconsistent."""


def load_spec(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise SpecError("The YAML root must be a mapping.")
    try:
        return resolve_process_defaults(data)
    except ValueError as exc:
        raise SpecError(str(exc)) from exc


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise SpecError(f"'{key}' must be a mapping.")
    return value


def _positive(parent: dict[str, Any], key: str) -> float:
    value = parent.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise SpecError(f"'{key}' must be a positive number.")
    return float(value)


def circular_segment_count(radius_um: float, target_deviation_nm: float) -> tuple[int, float]:
    """Meet an upper bound on vertex-to-two-neighbour-chord distance.

    This is NOT segment sagitta R*(1-cos(pi/N)). Use ceil, never nearest N.
    The half-angle form avoids cancellation at small tolerances.
    """
    if not math.isfinite(radius_um) or not math.isfinite(target_deviation_nm) or radius_um <= 0:
        raise SpecError("Circular tessellation inputs must be finite and positive.")
    target_um = target_deviation_nm / 1000.0
    if target_um <= 0 or target_um >= radius_um:
        raise SpecError("Circular tessellation target must be positive and smaller than radius.")
    delta = 2.0 * math.asin(math.sqrt(target_um / (2.0 * radius_um)))
    segments = max(8, math.ceil(2.0 * math.pi / delta))
    achieved_nm = 2 * radius_um * math.sin(math.pi / segments)**2 * 1000.0
    if achieved_nm > target_deviation_nm:  # Round-off at an exact integer bound.
        segments += 1
        achieved_nm = 2 * radius_um * math.sin(math.pi / segments)**2 * 1000.0
    return segments, achieved_nm


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        spec = resolve_process_defaults(spec)
    except ValueError as exc:
        raise SpecError(str(exc)) from exc
    design = _mapping(spec, "design")
    layers = _mapping(spec, "layers")
    unit = _mapping(spec, "unit_cell")
    waveguide = _mapping(spec, "waveguide")
    export = _mapping(spec, "export")

    for key in ("name", "top_cell", "mode", "source_intent"):
        if not isinstance(design.get(key), str) or not design[key].strip():
            raise SpecError(f"design.{key} must be a non-empty string.")
    if design["mode"] not in {"new", "live-edit", "legacy-migration"}:
        raise SpecError("design.mode must be new, live-edit, or legacy-migration.")
    dbu_um = _positive(design, "dbu_um")

    for logical_name, value in layers.items():
        if not (
            isinstance(logical_name, str)
            and isinstance(value, list)
            and len(value) == 2
            and all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 65535 for item in value)
        ):
            raise SpecError(f"layers.{logical_name} must be [nonnegative layer, datatype].")
    if "device" not in layers:
        raise SpecError("layers.device is required.")

    if unit.get("family") != "microring":
        raise SpecError("The reference generator currently supports unit_cell.family=microring.")
    parameters = _mapping(unit, "parameters")
    radius_um = _positive(parameters, "radius_um")
    ring_width_um = _positive(parameters, "width_um")
    if ring_width_um >= 2.0 * radius_um:
        raise SpecError("Ring width must be smaller than the diameter.")

    tessellation = _mapping(unit, "tessellation")
    target_nm = _positive(tessellation, "midpoint_chord_deviation_nm")
    if dbu_um * 1000.0 > target_nm / 5.0:
        raise SpecError(
            "design.dbu_um is too coarse for the requested ring deviation; "
            "use a DBU no larger than one fifth of the target."
        )
    # Protect the worst (outer) boundary and reserve quantization error. A
    # rounded point moves <= DBU/sqrt(2), so point/chord distance can move by
    # <= sqrt(2)*DBU. Saved coordinates must still meet the original upper bound.
    budget_nm = target_nm - math.sqrt(2) * dbu_um * 1000
    segments, achieved_nm = circular_segment_count(radius_um + ring_width_um / 2, budget_nm)
    extent = design.get("extent_um")
    if extent is not None:
        try:
            check_dbu_extent(dbu_um, extent)
        except ValueError as exc:
            raise SpecError(str(exc)) from exc

    bus_width_um = _positive(waveguide, "width_um")
    gap_um = waveguide.get("coupling_gap_um")
    if not isinstance(gap_um, (int, float)) or isinstance(gap_um, bool) or not math.isfinite(gap_um) or gap_um < 0:
        raise SpecError("waveguide.coupling_gap_um must be nonnegative.")
    coupling_length_um = _positive(waveguide, "coupling_length_um")
    if waveguide.get("route_kind") != "euler-edge-transition":
        raise SpecError("The reference generator requires route_kind=euler-edge-transition.")

    euler = _mapping(waveguide, "euler")
    euler_radius_um = _positive(euler, "min_radius_um")
    points_per_90 = euler.get("points_per_90_deg")
    if not isinstance(points_per_90, int) or isinstance(points_per_90, bool) or points_per_90 < 32:
        raise SpecError("waveguide.euler.points_per_90_deg must be an integer >= 32.")

    for edge_name in ("left_edge", "right_edge"):
        edge = _mapping(waveguide, edge_name)
        _positive(edge, "straight_length_um")
        drop = edge.get("vertical_drop_um")
        if not isinstance(drop, (int, float)) or isinstance(drop, bool) or not math.isfinite(drop) or drop < 0:
            raise SpecError(f"waveguide.{edge_name}.vertical_drop_um must be nonnegative.")

    ports = spec.get("ports")
    if not isinstance(ports, list) or len(ports) < 2:
        raise SpecError("At least two ports are required.")
    names: list[str] = []
    for port in ports:
        if not isinstance(port, dict) or not isinstance(port.get("name"), str):
            raise SpecError("Each port must be a mapping with a string name.")
        names.append(port["name"])
    if len(names) != len(set(names)):
        raise SpecError("Port names must be unique.")

    allowlist = export.get("allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        raise SpecError("export.allowlist must be a non-empty list.")
    unknown_layers = [name for name in allowlist if name not in layers]
    if unknown_layers:
        raise SpecError(f"export.allowlist references unknown layers: {unknown_layers}")
    if "device" not in allowlist:
        raise SpecError("The reference generator requires device in export.allowlist.")

    return {
        "ok": True,
        "design_name": design["name"],
        "top_cell": design["top_cell"],
        "dbu_um": dbu_um,
        "ring": {
            "radius_um": radius_um,
            "width_um": ring_width_um,
            "inner_radius_um": radius_um - ring_width_um / 2.0,
            "outer_radius_um": radius_um + ring_width_um / 2.0,
            "target_midpoint_chord_deviation_nm": target_nm,
            "segments": segments,
            "achieved_analytic_deviation_nm": achieved_nm,
            "analytic_metric_boundary": "outer",
            "quantization_budget_nm": target_nm - budget_nm,
        },
        "waveguide": {
            "width_um": bus_width_um,
            "coupling_gap_um": float(gap_um),
            "coupling_length_um": coupling_length_um,
            "euler_min_radius_um": euler_radius_um,
            "points_per_90_deg": points_per_90,
        },
        "ports": names,
        "export_layers": allowlist,
        "resolved_process": spec.get("process"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = validate_spec(load_spec(args.spec))
    except (OSError, yaml.YAMLError, SpecError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
