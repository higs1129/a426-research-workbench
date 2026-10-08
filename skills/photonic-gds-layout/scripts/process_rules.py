#!/usr/bin/env python3
"""User SiN process defaults and focused, semantic KLayout geometry checks.

All geometry passed to checks uses the layout's integer DBU coordinates.
These checks supplement a declared design specification; they are not a DRC deck.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from copy import deepcopy
from decimal import Decimal
import json
import math
from pathlib import Path
from typing import Iterable

import klayout.db as kdb


def load_profile(path: str | Path | None = None) -> dict:
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "assets" / "sin-user-process.json"
    return json.loads(path.read_text(encoding="utf-8"))


def layers_for_writefield(size_um: int | float, profile: dict | None = None) -> dict[str, tuple[int, int]]:
    profile = profile or load_profile()
    key = format(Decimal(str(size_um)).normalize(), "f")
    if key not in profile["exposure_datatypes"]:
        raise ValueError(f"No approved writefield datatype for {size_um} um; declare a process profile")
    datatype = profile["exposure_datatypes"][key]
    layers = {name: tuple(pair) for name, pair in profile["fixed_layers"].items()}
    layers.update({name: (number, datatype) for name, number in profile["exposure_layers"].items()})
    return layers


def resolve_process_defaults(spec: dict) -> dict:
    """Resolve the user's explicit SiN profile; never silently overwrite overrides.

    Missing process group keeps legacy/synthetic specs usable. The maintained
    intake template selects this profile by default for this user's SiN work.
    Custom/non-SiN profiles must supply their own resolver and rule sources.
    """
    result = deepcopy(spec)
    process = result.get("process", {})
    if process.get("profile") != "sin-user-process":
        return result
    profile = load_profile()
    groups = process.get("exposure_groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("SiN profile requires exposure_groups with id and writefield_size_um")
    resolved = {}
    for group in groups:
        name = group.get("id")
        if not isinstance(name, str) or not name or name in resolved:
            raise ValueError("Exposure group ids must be unique nonempty strings")
        resolved[name] = {key: list(pair) for key, pair in layers_for_writefield(group.get("writefield_size_um"), profile).items()}
    process["resolved_layers_by_group"] = resolved
    ports = deepcopy(profile["ports"])
    ports.update(process.get("port_overrides", {}))
    for key, value in ports.items():
        if key.endswith("_um") and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0):
            raise ValueError(f"Positive finite port default required: {key}")
    if not math.isclose(ports["narrow_total_length_um"], ports["narrow_inside_length_um"] + ports["narrow_outside_length_um"], rel_tol=0, abs_tol=1e-9):
        raise ValueError("Narrow section total must equal inside plus outside; update dependent lengths")
    process["resolved_port_defaults"] = ports
    process["profile_version"] = profile["version"]
    process["resolved_tessellation"] = deepcopy(profile["tessellation"])
    if "unit_cell" in result:
        tessellation = result["unit_cell"].setdefault("tessellation", {})
        if tessellation.get("midpoint_chord_deviation_nm") is None:
            tessellation["midpoint_chord_deviation_nm"] = profile["tessellation"]["sin_three_point_distance_upper_nm"]
        elif tessellation["midpoint_chord_deviation_nm"] > profile["tessellation"]["sin_three_point_distance_upper_nm"]:
            raise ValueError("SiN three-point distance must be <0.1 nm; declare a different sourced process for another limit")
    if len(groups) == 1:
        expected = next(iter(resolved.values()))
        layers = result.setdefault("layers", {})
        for name in list(layers):
            role = "sin" if name == "device" else name
            if role not in expected:
                continue
            if layers[name] is None:
                layers[name] = expected[role]
            elif list(layers[name]) != expected[role]:
                raise ValueError(f"{name} layer conflicts with exposure profile; declare a custom profile for an intentional change")
        layers.setdefault("device", expected["sin"])
    return result


def format_nm_as_um(value: int | float | str | Decimal) -> str:
    """Exact decimal conversion with no precision rounding: 900 -> .9um."""
    number = Decimal(str(value)) / Decimal(1000)
    if not number.is_finite():
        raise ValueError("Annotation dimensions must be finite")
    result = format(number, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    if number == 0:
        result = "0"
    elif result.startswith("0."):
        result = result[1:]
    elif result.startswith("-0."):
        result = "-" + result[2:]
    return result + "um"


def dimension_label(title: str, value_nm: int | float | str) -> str:
    if not title or len(title) > 3:
        raise ValueError("Mask short title must contain 1–3 characters")
    return f"{title} {format_nm_as_um(value_nm)}"


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _box_key(box: kdb.Box) -> tuple[int, int, int, int]:
    return (box.left, box.bottom, box.right, box.top)


def writefield_boxes(origins_um: Iterable[tuple[float, float]], size_um: float, dbu_um: float,
                     profile: dict | None = None) -> list[kdb.Box]:
    """Return individual solid field boxes; remove only exactly duplicate origins.

    Reject unrepresentable boundaries rather than silently changing field position.
    """
    from geometry_checks import check_dbu_extent

    def finite_number(value):
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) and math.isfinite(value)

    if not finite_number(size_um) or not finite_number(dbu_um) or size_um <= 0 or dbu_um <= 0:
        raise ValueError("Writefield size and DBU must be finite and positive")
    layers_for_writefield(size_um, profile)
    origins = list(origins_um)
    for origin in origins:
        if not isinstance(origin, (list, tuple)) or len(origin) != 2 or not all(finite_number(v) for v in origin):
            raise ValueError("Writefield origins must be finite [x,y] coordinates")
    if origins:
        extent = [min(p[0] for p in origins), min(p[1] for p in origins),
                  max(p[0] for p in origins) + size_um, max(p[1] for p in origins) + size_um]
        # Check the full set, not each field alone: opposite signed positions
        # may individually fit while the assembly span exceeds downstream limits.
        try:
            check_dbu_extent(dbu_um, extent)
        except OverflowError as exc:
            raise ValueError("Writefield coordinates exceed the chosen DBU integer range") from exc
    def quantize(value):
        units = Decimal(str(value)) / Decimal(str(dbu_um))
        if units != units.to_integral_value():
            raise ValueError(f"Writefield boundary {value} um is not representable at DBU {dbu_um}")
        return int(units)
    size = quantize(size_um)
    result = {}
    for x, y in origins:
        left, bottom = quantize(x), quantize(y)
        box = kdb.Box(left, bottom, left + size, bottom + size)
        result[_box_key(box)] = box
    return list(result.values())


def validate_writefields(cell: kdb.Cell, layer_index: int, expected: Iterable[kdb.Box]) -> list[Finding]:
    """Read actual recursive geometry; require one filled rectangle per expected field.

    Pass layer 30/datatype and expected boxes for each exposure group separately.
    A frame, PATH, merged adjacent rectangle, duplicate instance or wrong position fails.
    """
    findings = []
    actual = []
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        if not (shape.is_box() or shape.is_polygon() or shape.is_simple_polygon()):
            findings.append(Finding("error", "writefield_non_polygon", "Writefield must be a solid rectangle, not PATH/TEXT"))
        else:
            polygon = shape.polygon.transformed(iterator.trans())
            box = polygon.bbox()
            if polygon.holes() or polygon.area() != box.area() or box.area() <= 0:
                findings.append(Finding("error", "writefield_not_solid_rectangle", "Writefield shape does not fill its rectangular bounds"))
            actual.append(_box_key(box))
        iterator.next()
    if len(actual) != len(set(actual)):
        findings.append(Finding("error", "duplicate_writefield", "Repeated writefield geometry remains in saved hierarchy"))
    expected_keys = {_box_key(box) for box in expected}
    if set(actual) != expected_keys:
        findings.append(Finding("error", "writefield_mismatch", "Saved fields differ from individual expected rectangles (missing, merged, displaced or extra fields)"))
    return findings


def validate_layer_assignment(role: str, actual_layer: tuple[int, int], field_size_um: float,
                              profile: dict | None = None) -> list[Finding]:
    expected = layers_for_writefield(field_size_um, profile).get(role)
    if expected is None:
        raise ValueError(f"Unknown semantic layer role: {role}")
    return [] if tuple(actual_layer) == expected else [Finding("error", "wrong_layer", f"{role}: expected {expected}, found {actual_layer}")]


def check_field_containment(full_geometry: kdb.Region, role: str, actual_layer: tuple[int, int],
                            fields: Iterable[kdb.Box], override_reason: str | None = None) -> list[Finding]:
    """Check full polygons, not centerlines, for one-field SiN containment.

    A warning remains visible even with an accepted override. UV geometry is exempt.
    Pass only fields belonging to this feature's exposure group/datatype.
    """
    if actual_layer[0] != 1:
        return []
    if full_geometry.is_empty():
        return [Finding("error", "empty_feature", f"{role}: no polygon geometry supplied")]
    fields = list(fields)
    if any((full_geometry - kdb.Region(box)).is_empty() for box in fields):
        return []
    reason = f" Accepted exception: {override_reason.strip()}" if override_reason and override_reason.strip() else " Re-route globally or document the necessary exception."
    return [Finding("warning", "sin_feature_crosses_field", f"{role}: full feature width is not contained in one exposure field.{reason}")]


def validate_annotation_geometry(geometry: kdb.Region, actual_layer: tuple[int, int], kind: str,
                                 field_size_um: float, *, has_text_or_path: bool = False,
                                 forbidden_geometry: kdb.Region | None = None,
                                 declared_clearance_dbu: int | None = None) -> list[Finding]:
    """Validate supplied text polygons against layer and declared collision keepouts.

    forbidden_geometry can include structures and die-boundary keepout strips.
    Minimum stroke and clearance require sourced process values, not guessed defaults.
    """
    if kind not in ("optical", "electrical"):
        raise ValueError("Annotation kind must be optical or electrical")
    findings = validate_layer_assignment(kind + "_text", actual_layer, field_size_um)
    if has_text_or_path:
        findings.append(Finding("error", "annotation_not_polygon", "Mask annotation contains TEXT/PATH; convert glyphs to filled polygons"))
    if geometry.is_empty():
        findings.append(Finding("error", "empty_annotation", "No text polygon geometry supplied"))
    if declared_clearance_dbu is not None and declared_clearance_dbu < 0:
        raise ValueError("Clearance cannot be negative")
    if forbidden_geometry is not None:
        # One DBU expansion detects touching boundaries without inventing a process clearance.
        clearance = max(1, declared_clearance_dbu or 0)
        if not (geometry.sized(clearance) & forbidden_geometry).is_empty():
            findings.append(Finding("error", "annotation_collision", "Annotation touches a protected structure/boundary or violates declared clearance"))
    return findings


def validate_annotation_cell(cell: kdb.Cell, kind: str, field_size_um: float, **geometry_options) -> list[Finding]:
    """Inspect an explicitly annotation-only cell after GDS read-back.

    Checks every populated layer in this cell's hierarchy, including actual TEXT/PATH
    elements. Do not pass a whole device cell containing non-annotation geometry.
    """
    findings = []
    populated = False
    layout = cell.layout()
    for layer_index in layout.layer_indexes():
        iterator = cell.begin_shapes_rec(layer_index)
        if iterator.at_end():
            continue
        populated = True
        region = kdb.Region()
        non_polygon = False
        while not iterator.at_end():
            shape = iterator.shape()
            if shape.is_box() or shape.is_polygon() or shape.is_simple_polygon():
                region.insert(shape.polygon.transformed(iterator.trans()))
            else:
                non_polygon = True
            iterator.next()
        info = layout.get_info(layer_index)
        findings.extend(validate_annotation_geometry(region, (info.layer, info.datatype), kind,
                                                      field_size_um, has_text_or_path=non_polygon,
                                                      **geometry_options))
    if not populated:
        findings.append(Finding("error", "empty_annotation", "Annotation cell contains no geometry"))
    return findings


def validate_pad_groups(device_kind: str, groups: list[dict], accepted_components: dict) -> list[Finding]:
    """Compare fixed group-local pad centers/sizes while allowing independent anchors.

    Each group: component_profile, anchor_um=[x,y], local_pads=[{center_um,size_um}].
    accepted_components maps profile name to device_kind, source and local_pads.
    No alignment of separate groups is inferred or enforced.
    """
    if device_kind not in ("single", "array"):
        raise ValueError("Declare single or array device_kind")
    if not isinstance(accepted_components, dict):
        raise ValueError("Accepted pad components must be a profile mapping")
    if not isinstance(groups, (list, tuple)) or not groups:
        return [Finding("error", "pad_groups_missing", "At least one explicit pad group is required")]

    def finite_pair(value, positive=False):
        return (isinstance(value, (list, tuple)) and len(value) == 2
                and all(isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)
                        and math.isfinite(v) and (not positive or v > 0) for v in value))

    def valid_local_pads(value):
        return (isinstance(value, (list, tuple)) and len(value) > 0
                and all(isinstance(pad, dict) and finite_pair(pad.get("center_um"))
                        and finite_pair(pad.get("size_um"), positive=True) for pad in value))

    findings = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            findings.append(Finding("error", "pad_group_invalid", f"Pad group {index} must be a mapping"))
            continue
        component = accepted_components.get(group.get("component_profile"))
        if not isinstance(component, dict) or not isinstance(component.get("source"), str) or not component["source"].strip():
            findings.append(Finding("error", "pad_source_missing", f"Pad group {index} needs a sourced accepted component"))
            continue
        if component.get("device_kind") != device_kind:
            findings.append(Finding("error", "pad_device_kind", f"Pad group {index} uses a different device-kind profile"))
        if not valid_local_pads(component.get("local_pads")):
            findings.append(Finding("error", "pad_component_geometry_invalid", f"Pad group {index} accepted component needs nonempty finite pad centers and positive sizes"))
        if not valid_local_pads(group.get("local_pads")):
            findings.append(Finding("error", "pad_group_geometry_invalid", f"Pad group {index} needs nonempty finite pad centers and positive sizes"))
        elif valid_local_pads(component.get("local_pads")) and group["local_pads"] != component["local_pads"]:
            findings.append(Finding("error", "pad_group_changed", f"Pad group {index} changed fixed local pad geometry/probe spacing"))
        if not finite_pair(group.get("anchor_um")):
            findings.append(Finding("error", "pad_anchor_missing", f"Pad group {index} needs an independent finite [x,y] anchor"))
    return findings
