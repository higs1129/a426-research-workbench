from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from generate_layout import generate  # noqa: E402
import generate_layout
import yaml


def test_reference_layout_round_trips_through_klayout(tmp_path):
    data = yaml.safe_load(Path(__file__).with_name("design-spec-microring-euler.yaml").read_text(encoding="utf-8"))
    data["waveguide"]["euler"]["min_radius_um"] = 10
    spec = tmp_path / "short-path-spec.yaml"
    spec.write_text(yaml.safe_dump(data), encoding="utf-8")
    gds = tmp_path / "reference.gds"
    report_path = tmp_path / "verification.json"
    report = generate(spec, gds, report_path, shape_representation="path")

    assert report["ok"] is True
    assert gds.exists()
    assert report["verification"]["checks"]["ring_segment_count_matches"] is True
    assert report["verification"]["checks"]["ring_deviation_within_bound"] is True
    assert report["verification"]["checks"]["route_is_continuous_single_path"] is True


def test_reference_layout_expands_paths_to_polygons(tmp_path):
    spec = Path(__file__).with_name("design-spec-microring-euler.yaml")
    gds = tmp_path / "reference-polygon.gds"
    report_path = tmp_path / "verification-polygon.json"
    report = generate(spec, gds, report_path, shape_representation="polygon")

    assert report["ok"] is True
    assert gds.exists()
    assert report["shape_representation"] == "polygon"
    assert report["verification"]["checks"]["device_path_count_is_zero"] is True
    assert report["verification"]["checks"]["all_device_shapes_are_polygons"] is True
    assert report["verification"]["checks"]["route_is_connected_without_holes"] is True
    assert report["verification"]["checks"]["route_boundary_within_bound"] is True
    assert report["verification"]["checks"]["ring_boundaries_deviation_within_bound"] is True
    assert report["verification"]["checks"]["saved_geometry_matches_source"] is True


def test_failed_candidate_keeps_current_delivery(tmp_path, monkeypatch):
    spec = Path(__file__).with_name("design-spec-microring-euler.yaml")
    gds = tmp_path / "current.gds"
    before = b"existing user delivery must survive failed verification"
    gds.write_bytes(before)
    original = generate_layout.verify_polygon_readback

    def fail(*args, **kwargs):
        report = original(*args, **kwargs)
        report["checks"]["synthetic_required_check"] = False
        return report

    monkeypatch.setattr(generate_layout, "verify_polygon_readback", fail)
    result = generate(spec, gds, tmp_path / "failure.json")
    assert not result["ok"]
    assert gds.read_bytes() == before
    assert Path(result["candidate_if_failed"]).exists()
