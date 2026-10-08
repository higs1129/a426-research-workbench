from pathlib import Path
import sys

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_design_spec import SpecError, circular_segment_count, load_spec, validate_spec  # noqa: E402


def test_reference_spec_derives_requested_ring_precision():
    spec = load_spec(Path(__file__).with_name("design-spec-microring-euler.yaml"))
    report = validate_spec(spec)
    assert report["ring"]["segments"] > 6283
    assert report["ring"]["achieved_analytic_deviation_nm"] + report["ring"]["quantization_budget_nm"] <= 0.1
    assert report["ring"]["inner_radius_um"] == 199.0
    assert report["ring"]["outer_radius_um"] == 201.0


def test_coarse_dbu_is_rejected():
    spec = load_spec(Path(__file__).with_name("design-spec-microring-euler.yaml"))
    spec["design"]["dbu_um"] = 0.001
    with pytest.raises(SpecError, match="too coarse"):
        validate_spec(spec)


def test_segment_formula_is_monotonic_for_tighter_targets():
    loose_segments, _ = circular_segment_count(200.0, 1.0)
    tight_segments, _ = circular_segment_count(200.0, 0.1)
    assert tight_segments > loose_segments


def test_nearest_integer_would_break_upper_bound():
    segments, achieved = circular_segment_count(200.0, 0.1)
    assert segments == 6284
    assert achieved <= 0.1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_nonfinite_or_boolean_geometry_is_rejected(value):
    spec = load_spec(Path(__file__).with_name("design-spec-microring-euler.yaml"))
    spec["unit_cell"]["parameters"]["radius_um"] = value
    with pytest.raises(SpecError):
        validate_spec(spec)
