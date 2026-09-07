from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from generate_layout import generate  # noqa: E402


def test_reference_layout_round_trips_through_klayout(tmp_path):
    spec = Path(__file__).with_name("design-spec-microring-euler.yaml")
    gds = tmp_path / "reference.gds"
    report_path = tmp_path / "verification.json"
    report = generate(spec, gds, report_path)

    assert report["ok"] is True
    assert gds.exists()
    assert report["verification"]["checks"]["ring_segment_count_matches"] is True
    assert report["verification"]["checks"]["ring_deviation_near_target"] is True
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
    assert report["verification"]["checks"]["device_polygon_count_is_five"] is True
    assert report["verification"]["checks"]["route_is_single_polygon"] is True
