"""Synthetic acceptance contracts for geometry preservation and source rebuilds."""

from pathlib import Path
import sys

import klayout.db as kdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from geometry_checks import compare_geometry, compare_vertices
from verify_rebuild_isolation import run_isolated_rebuild


SKILL_TEST_ROOT = Path(__file__).resolve().parent


def polygon_layout(points, dbu=0.001, name="TOP", path=False):
    layout = kdb.Layout()
    layout.dbu = dbu
    cell = layout.create_cell(name)
    layer = layout.layer(10, 0)
    dbu_points = [kdb.Point(round(x / dbu), round(y / dbu)) for x, y in points]
    cell.shapes(layer).insert(kdb.Path(dbu_points, round(1 / dbu)) if path else kdb.Polygon(dbu_points))
    return layout


def test_collinear_vertex_deletion_keeps_xor_zero_but_fails_vertex_contract():
    # PATH centerline stations retain the redundant collinear sampling point;
    # their expanded mask remains geometrically equivalent after deletion.
    reference = polygon_layout([(0, 0), (10, 0), (10, 5), (5, 5), (0, 5)], path=True)
    candidate = polygon_layout([(0, 0), (10, 0), (10, 5), (0, 5)], path=True)

    assert compare_geometry(reference, candidate, "TOP", [(10, 0)])["ok"]
    result = compare_vertices(reference, candidate, "TOP", [(10, 0)])
    assert not result["ok"]
    assert result["layers"][0]["reference_vertices"] == 5
    assert result["layers"][0]["candidate_vertices"] == 4


def transformed_layout(dbu):
    layout = kdb.Layout()
    layout.dbu = dbu
    layer = layout.layer(1, 0)
    child = layout.create_cell("CHILD")
    child.shapes(layer).insert(kdb.Polygon([
        kdb.Point(round(x / dbu), round(y / dbu)) for x, y in [(0, 0), (2, 0), (2, 1)]
    ]))
    middle = layout.create_cell("MIDDLE")
    middle.insert(kdb.CellInstArray(
        child.cell_index(), kdb.CplxTrans(2, 90, True, round(30 / dbu), round(40 / dbu))
    ))
    top = layout.create_cell("TOP")
    top.insert(kdb.CellInstArray(
        middle.cell_index(), kdb.CplxTrans(1, 180, False, round(100 / dbu), round(50 / dbu))
    ))
    return layout


def test_nested_magnification_rotation_mirror_translation_and_dbu_compare_in_physical_space():
    reference = transformed_layout(0.001)
    candidate = transformed_layout(0.0005)

    assert compare_geometry(reference, candidate, "TOP", [(1, 0)])["ok"]
    assert compare_vertices(reference, candidate, "TOP", [(1, 0)])["ok"]


def nonbinary_dbu_layout(dbu, magnification):
    layout = kdb.Layout()
    layout.dbu = dbu
    layer = layout.layer(1, 0)
    child = layout.create_cell("C")
    child.shapes(layer).insert(kdb.Box(0, 0, 3, 3))
    top = layout.create_cell("TOP")
    top.insert(kdb.CellInstArray(child.cell_index(), kdb.ICplxTrans(magnification, 0, False, 0, 0)))
    return layout


def test_nonbinary_magnification_and_dbu_roundoff_is_not_a_geometry_change():
    reference = nonbinary_dbu_layout(0.00005, 0.8)
    candidate = nonbinary_dbu_layout(0.00004, 1.0)

    assert compare_geometry(reference, candidate, "TOP", [(1, 0)])["ok"]
    assert compare_vertices(reference, candidate, "TOP", [(1, 0)])["ok"]


def test_real_small_displacement_still_fails_both_contracts():
    reference = polygon_layout([(0, 0), (3, 0), (3, 3), (0, 3)], dbu=0.000001)
    candidate = polygon_layout([(0.000001, 0), (3.000001, 0), (3.000001, 3), (0.000001, 3)], dbu=0.000001)

    assert not compare_geometry(reference, candidate, "TOP", [(10, 0)])["ok"]
    assert not compare_vertices(reference, candidate, "TOP", [(10, 0)])["ok"]


def test_representable_isolated_addition_or_gap_in_far_large_geometry_fails():
    reference = kdb.Layout()
    reference.dbu = 0.00005
    top = reference.create_cell("TOP")
    layer = reference.layer(10, 0)
    top.shapes(layer).insert(kdb.Box(200000000, 200000000, 400000000, 400000000))

    added = reference.dup()
    added.cell("TOP").shapes(added.layer(10, 0)).insert(
        kdb.Box(420000000, 420000000, 420000020, 420000020)
    )
    assert not compare_geometry(reference, added, "TOP", [(10, 0)])["ok"]

    gap = reference.dup()
    gap_top = gap.cell("TOP")
    gap_top.shapes(gap.layer(10, 0)).clear()
    gap_top.shapes(gap.layer(10, 0)).insert(kdb.Box(200000000, 200000000, 300000000, 400000000))
    gap_top.shapes(gap.layer(10, 0)).insert(kdb.Box(300000020, 200000000, 400000000, 400000000))
    assert not compare_geometry(reference, gap, "TOP", [(10, 0)])["ok"]


def test_metal_polygon_split_is_geometry_equivalent_but_not_vertex_preserving():
    reference = kdb.Layout()
    reference.dbu = 0.001
    ref = reference.create_cell("TOP")
    layer = reference.layer(10, 0)
    ref.shapes(layer).insert(kdb.Box(0, 0, 10000, 10000))

    candidate = kdb.Layout()
    candidate.dbu = 0.001
    cand = candidate.create_cell("TOP")
    layer = candidate.layer(10, 0)
    cand.shapes(layer).insert(kdb.Box(0, 0, 5000, 10000))
    cand.shapes(layer).insert(kdb.Box(5000, 0, 10000, 10000))

    assert compare_geometry(reference, candidate, "TOP", [(10, 0)])["ok"]
    assert not compare_vertices(reference, candidate, "TOP", [(10, 0)])["ok"]


def test_isolated_rebuild_reports_retired_dependency_and_accepts_source_only_build(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "history").mkdir()
    (tmp_path / "src" / "value.txt").write_text("source-value", encoding="utf-8")
    (tmp_path / "history" / "retired.json").write_text("retired", encoding="utf-8")
    (tmp_path / "old-output.json").write_text("stale", encoding="utf-8")
    (tmp_path / "build.py").write_text(
        "import argparse\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser(); p.add_argument('--output'); p.add_argument('--use-history', action='store_true'); a=p.parse_args()\n"
        "if a.use_history: Path('history/retired.json').read_text()\n"
        "Path(a.output).write_text(Path('src/value.txt').read_text())\n",
        encoding="utf-8",
    )

    isolation_root = SKILL_TEST_ROOT / ".runs" / "rebuild-isolation"
    isolation_root.mkdir(parents=True, exist_ok=True)
    old_result = run_isolated_rebuild(
        tmp_path, [sys.executable, "-c", "pass"], "old-output.json",
        unavailable=["history/retired.json"], isolation_root=isolation_root,
    )
    assert not old_result["ok"]
    assert old_result["returncode"] == 0
    assert not old_result["generated"]
    assert not old_result["output_exists"]

    def valid_output(path):
        return path.read_text(encoding="utf-8") == "source-value"

    source_result = run_isolated_rebuild(
        tmp_path, [sys.executable, "build.py", "--output", "source.json"], "source.json",
        unavailable=["history/retired.json"], isolation_root=isolation_root,
        output_validator=valid_output,
    )
    assert source_result["ok"]
    assert source_result["generated"]
    assert source_result["verified"]
    assert source_result["output_exists"]

    invalid_result = run_isolated_rebuild(
        tmp_path, [sys.executable, "build.py", "--output", "invalid.json"], "invalid.json",
        unavailable=["history/retired.json"], isolation_root=isolation_root,
        output_validator=lambda path: False,
    )
    assert not invalid_result["ok"]
    assert invalid_result["generated"]
    assert not invalid_result["verified"]


def test_isolation_root_must_be_within_allowed_root(tmp_path):
    with pytest.raises(ValueError, match="inside"):
        run_isolated_rebuild(
            tmp_path, [sys.executable, "-c", "pass"], "out.json",
            isolation_root=tmp_path, allowed_root=SKILL_TEST_ROOT,
        )


def test_isolation_root_inside_project_is_rejected_without_touching_source(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    marker = project / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    isolation_root = project / "tests" / ".runs"
    isolation_root.mkdir(parents=True)

    with pytest.raises(ValueError, match="must not overlap"):
        run_isolated_rebuild(
            project, [sys.executable, "-c", "pass"], "out.json",
            isolation_root=isolation_root, allowed_root=project / "tests",
        )
    assert marker.read_text(encoding="utf-8") == "unchanged"
