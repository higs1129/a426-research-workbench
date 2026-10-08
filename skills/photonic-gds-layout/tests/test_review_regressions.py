"""Independent-review counterexamples exercised through actual GDS delivery."""
from copy import deepcopy
from pathlib import Path
import sys

import klayout.db as kdb
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_layout as generator
from validate_design_spec import SpecError


def spec_data():
    data = yaml.safe_load(Path(__file__).with_name("design-spec-microring-euler.yaml").read_text(encoding="utf-8"))
    data["process"] = {"profile": "sin-user-process", "exposure_groups": [{"id": "main", "writefield_size_um": 500}]}
    return data


def save_spec(tmp_path, data):
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_reported_256_point_euler_case_is_resampled_and_saved_boundary_passes(tmp_path):
    data = spec_data()
    output = tmp_path / "route.gds"
    report = generator.generate(save_spec(tmp_path, data), output, tmp_path / "report.json")
    assert report["ok"]
    waveguide = report["validation"]["waveguide"]
    assert waveguide["requested_points_per_90_deg"] == 256
    assert waveguide["points_per_90_deg"] > 2000
    boundary = report["verification"]["readback"]["route_boundary"]
    assert boundary["max_deviation_nm"] < .1
    assert boundary["checked_vertices"] > 10000
    # Independently evaluate all saved smooth triples with short adjacent edges,
    # as in the external review, after removing only internal fragment boundaries.
    layout = kdb.Layout()
    layout.read(str(output))
    route = layout.cell(data["design"]["top_cell"] + "__route")
    polygons = list(kdb.Region(route.begin_shapes_rec(layout.find_layer(1, 0))).merged().each())
    assert len(polygons) == 1 and polygons[0].holes() == 0
    points = [(p.x*layout.dbu, p.y*layout.dbu) for p in polygons[0].each_point_hull()]
    distances = []
    import math
    for i, point in enumerate(points):
        a, b = points[i-1], points[(i+1) % len(points)]
        if math.dist(a, point) < 2 and math.dist(b, point) < 2:
            distances.append(abs((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])) / math.dist(a, b) * 1000)
    assert max(distances) < .1


def test_old_coarse_euler_is_rejected_after_readback_and_preserves_delivery(tmp_path, monkeypatch):
    original_build = generator.build_route

    def coarse(spec, validation):
        altered = deepcopy(validation)
        altered["waveguide"]["points_per_90_deg"] = 256
        return original_build(spec, altered)

    monkeypatch.setattr(generator, "build_route", coarse)
    output = tmp_path / "existing.gds"
    output.write_bytes(b"preserve the previous accepted delivery")
    report = generator.generate(save_spec(tmp_path, spec_data()), output, tmp_path / "report.json")
    assert not report["ok"]
    assert not report["verification"]["checks"]["route_boundary_within_bound"]
    assert report["verification"]["readback"]["route_boundary"]["max_deviation_nm"] > 6
    assert output.read_bytes() == b"preserve the previous accepted delivery"
    assert Path(report["candidate_if_failed"]).exists()


def test_multiple_groups_cannot_emit_wrong_layer_or_ambiguous_reference_device(tmp_path):
    data = spec_data()
    data["process"]["exposure_groups"].append({"id": "large", "writefield_size_um": 1000})
    data["layers"]["device"] = [10, 1]
    output = tmp_path / "must-not-exist.gds"
    with pytest.raises((SpecError, ValueError)):
        generator.generate(save_spec(tmp_path, data), output, tmp_path / "report.json")
    assert not output.exists()
    # Even valid role mapping is beyond this single-device generator's scope.
    data["layers"]["device"] = [1, 0]
    data["process"]["layer_exposure_groups"] = {"device": "main"}
    with pytest.raises(SpecError, match="one exposure group"):
        generator.generate(save_spec(tmp_path, data), output, tmp_path / "report.json")
    assert not output.exists()


def test_resolved_dense_route_refuses_overlong_path_record(tmp_path):
    with pytest.raises(ValueError, match="PATH XY record limit"):
        generator.generate(save_spec(tmp_path, spec_data()), tmp_path / "path.gds", tmp_path / "report.json", shape_representation="path")


def test_single_1000um_profile_generates_only_expected_optical_datatype(tmp_path):
    data = spec_data()
    data["process"]["exposure_groups"][0]["writefield_size_um"] = 1000
    data["layers"]["device"] = None
    output = tmp_path / "large-field.gds"
    report = generator.generate(save_spec(tmp_path, data), output, tmp_path / "report.json")
    assert report["ok"]
    layout = kdb.Layout()
    layout.read(str(output))
    assert {(info.layer, info.datatype) for info in layout.layer_infos()} == {(1, 1)}
