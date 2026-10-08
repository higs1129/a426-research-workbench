"""Synthetic failure cases for geometry preservation and process resolution."""
import math
from pathlib import Path
import sys

import klayout.db as kdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from geometry_checks import (check_curve_fragment, check_dbu_extent, check_ports,
                             check_required_corridors, compare_geometry, shared_station_strip)
from process_rules import resolve_process_defaults


def test_full_span_and_absolute_coordinates_both_constrain_dbu():
    # +/-30 mm fits at .02 nm DBU, but the 60 mm span does not.
    with pytest.raises(ValueError, match="span"):
        check_dbu_extent(.00002, [-30000, -10, 30000, 10])
    assert check_dbu_extent(.00004, [-30000, -10, 30000, 10])["max_span_dbu"] == 1500000000
    # A tiny layout very far from the origin can fail despite small span.
    with pytest.raises(ValueError):
        check_dbu_extent(.001, [3000000, 0, 3000001, 1])


def test_paired_stations_keep_fragment_width_and_reject_wrong_join():
    angles = [i * .02 for i in range(60)]
    center = [(20*math.cos(t), 20*math.sin(t)) for t in angles]
    normals = [(math.cos(t), math.sin(t)) for t in angles]
    parts = shared_station_strip(center, normals, 2, max_stations=12)
    for part in parts:
        assert check_curve_fragment(part, 2, .43, 1e-9)["max_width_um"] == pytest.approx(2)
    # Independent boundary slicing once produced diagonal cuts across a spiral.
    wrong = parts[1].copy()
    wrong[-1] = parts[0][-1]
    with pytest.raises(ValueError, match="width/caps"):
        check_curve_fragment(wrong, 2, .43, 1e-9)
    for left, right in zip(parts, parts[1:]):
        n = len(left)//2
        assert left[n-1] == right[0]
        assert left[n] == right[-1]


def test_full_width_corridor_detects_neck_despite_connectivity():
    expected = kdb.Region(kdb.Box(0, 0, 100, 10))
    actual = kdb.Region(kdb.Box(0, 0, 45, 10)) + kdb.Region(kdb.Box(45, 4, 55, 6)) + kdb.Region(kdb.Box(55, 0, 100, 10))
    assert actual.merged().count() == 1
    with pytest.raises(ValueError, match="neck"):
        check_required_corridors(actual, expected)
    check_required_corridors(expected, expected)


@pytest.mark.parametrize("change", [{"width_um": 3}, {"layer": [10, 1]}, {"orientation_deg": 90}, {"center_um": [0, .1]}])
def test_port_chain_rejects_mismatch(change):
    first = {"center_um": [0, 0], "width_um": 2, "layer": [10, 0], "orientation_deg": 0}
    second = {**first, "orientation_deg": 180}
    check_ports(first, second)
    with pytest.raises(ValueError):
        check_ports(first, {**second, **change})


def test_protected_layer_xor_detects_same_bbox_same_count_change():
    layouts = [kdb.Layout(), kdb.Layout()]
    for i, layout in enumerate(layouts):
        layout.dbu = .001
        cell = layout.create_cell("TOP")
        layer = layout.layer(10, 0)
        # Both have bbox (0,0;100,100) and one polygon, but different solid masks.
        cell.shapes(layer).insert(kdb.Polygon([kdb.Point(0, 0), kdb.Point(100, 0),
                                              kdb.Point(100, 100), kdb.Point(i * 40, 100)]))
    assert not compare_geometry(*layouts, "TOP", [(10, 0)])["ok"]
    assert compare_geometry(layouts[0], layouts[0], "TOP", [(10, 0)])["ok"]


def test_profile_resolves_1000um_layers_without_changing_uv_datatypes():
    spec = {"process": {"profile": "sin-user-process", "exposure_groups": [{"id": "main", "writefield_size_um": 1000}]},
            "layers": {"device": None, "writefield": None, "electrode": [10, 0]}, "unit_cell": {}}
    result = resolve_process_defaults(spec)
    assert spec["layers"]["device"] is None  # Caller input preserved.
    assert result["layers"] == {"device": [1, 1], "writefield": [30, 1], "electrode": [10, 0]}
    assert result["unit_cell"]["tessellation"]["midpoint_chord_deviation_nm"] == .1
    assert result["process"]["resolved_port_defaults"]["linear_taper_length_um"] == 300
    spec["layers"]["electrode"] = [10, 1]
    with pytest.raises(ValueError, match="conflicts"):
        resolve_process_defaults(spec)


def test_profile_override_recomputes_related_lengths():
    spec = {"process": {"profile": "sin-user-process", "exposure_groups": [{"id": "x", "writefield_size_um": 500}],
                        "port_overrides": {"narrow_inside_length_um": 120}}}
    with pytest.raises(ValueError, match="total"):
        resolve_process_defaults(spec)
    spec["process"]["port_overrides"]["narrow_total_length_um"] = 220
    assert resolve_process_defaults(spec)["process"]["resolved_port_defaults"]["narrow_total_length_um"] == 220
