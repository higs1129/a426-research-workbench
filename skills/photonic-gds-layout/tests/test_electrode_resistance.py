"""Analytic limits, actual network power and failure cases; all inputs synthetic."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from electrode_resistance import (Material, Resistor, annular_arc, evaluate,
                                  linear_taper, solve_network, straight, thermal_proxy)


def material(rs=1.0):
    return Material(rs, {"test metal": 100.0}, "synthetic test value", "synthetic stack")


def branch(name, a, b, resistance, heater=False):
    return Resistor(name, a, b, resistance, heater, "synthetic network")


def solve(items):
    return solve_network(items, "supply", "return", 1.0, "dc_across_terminals")


def test_analytic_shapes_and_equal_width_limit():
    m = material(2)
    assert straight(m, 20, 4) == 10
    assert math.isclose(linear_taper(m, 30, 2, 8), 10 * math.log(4))
    assert math.isclose(linear_taper(m, 30, 8, 2), 10 * math.log(4))
    assert linear_taper(m, 30, 4, 4) == 15
    assert math.isclose(linear_taper(m, 30, 4, 4 + 1e-12), 15, rel_tol=1e-12)
    assert math.isclose(annular_arc(m, 10, 20, math.pi), 2 * math.pi / math.log(2))
    assert math.isclose(annular_arc(m, 100, 100.00001, math.pi),
                        straight(m, math.pi * 100.000005, .00001), rel_tol=1e-8)


def test_published_geometry_formula_regression_without_thermal_claim():
    # Representative U: 490 um straight + total pi arc, width 10, radius 80.
    # Historical Rs is supplied explicitly, never a production default.
    m = material(.842567)
    rh = straight(m, 490, 10) + annular_arc(m, 75, 85, math.pi)
    rt = 2 * linear_taper(m, 40, 10, 40)
    rl = straight(m, 2880, 40)
    assert math.isclose(rh, 62.434, abs_tol=.001)
    assert math.isclose(rt, 3.115, abs_tol=.001)
    assert math.isclose(rh + rt + rl, 126.214, abs_tol=.001)
    result = solve([branch("heater", "supply", "x", rh, True),
                    branch("tapers+leads", "x", "return", rt + rl)])
    assert math.isclose(result["heater_power_fraction"], .4947, abs_tol=.0001)
    assert math.isclose(result["heater_power_mw"], 3.919, abs_tol=.001)


def test_series_power_and_ghz_per_mw_to_ghz_per_v2_factor():
    result = solve([branch("heater", "supply", "mid", 100, True),
                    branch("lead", "mid", "return", 100)])
    assert result["equivalent_resistance_ohm"] == 200
    assert result["total_power_mw"] == 5
    assert result["heater_power_mw"] == 2.5
    assert result["heater_power_fraction"] == .5
    proxy = thermal_proxy(result, {"heater": 18}, "synthetic same-observable coefficient")
    assert proxy["beta_ghz_per_v2"] == 45  # 1000 * S * Rh / Rtotal**2


def test_parallel_arms_with_shared_supply_lead_use_branch_currents():
    result = solve([branch("shared", "supply", "split", 50),
                    branch("h1", "split", "return", 100, True),
                    branch("h2", "split", "return", 100, True)])
    assert result["equivalent_resistance_ohm"] == 100
    assert result["total_power_mw"] == 10
    assert result["heater_power_fraction"] == .5
    assert result["branches"]["h1"]["power_mw"] == 2.5
    assert thermal_proxy(result, {"h1": 2, "h2": 3}, "synthetic")["beta_ghz_per_v2"] == 12.5
    partial = thermal_proxy(result, {"h1": 2}, "synthetic")
    assert partial["unmodeled_heater_branches"] == ["h2"]


def test_network_errors_are_rejected():
    for items, message in [
        ([branch("h", "supply", "return", 100), branch("floating", "x", "y", 1)], "disconnected"),
        ([branch("h", "supply", "return", 100), branch("h", "supply", "return", 200)], "uniquely"),
        ([branch("h", "supply", "x", 100)], "distinct supply"),
    ]:
        with unittest.TestCase().assertRaisesRegex(ValueError, message):
            solve(items)


def test_invalid_dimensions_material_sources_and_voltage_are_rejected():
    with unittest.TestCase().assertRaisesRegex(ValueError, "source"):
        Material(.8, {"Pt": 200}, "", "test")
    with unittest.TestCase().assertRaisesRegex(ValueError, "positive"):
        Material(.8, {"Pt": 0}, "test", "test")
    for args in ((5, 4, 1), (0, 4, 1), (3, 4, 360)):
        with unittest.TestCase().assertRaises(ValueError):
            annular_arc(material(), *args)
    with unittest.TestCase().assertRaisesRegex(ValueError, "positive"):
        linear_taper(material(), 10, 0, 4)
    with unittest.TestCase().assertRaisesRegex(ValueError, "self-loop"):
        branch("bad", "a", "a", 2)
    with unittest.TestCase().assertRaisesRegex(ValueError, "positive"):
        branch("bad", "a", "b", -2)
    with unittest.TestCase().assertRaisesRegex(ValueError, "voltage_definition"):
        solve_network([branch("h", "supply", "return", 1)], "supply", "return", 1, "peak")
    with unittest.TestCase().assertRaisesRegex(ValueError, "declared heater"):
        thermal_proxy(solve([branch("lead", "supply", "return", 1)]), {"lead": 2}, "test")


def test_explicit_json_contract_preserves_material_and_voltage_metadata():
    result = evaluate({
        "material": {"sheet_resistance_ohm_per_square": 1, "layers_nm": {"test": 100},
                     "sheet_resistance_source": "synthetic", "thickness_source": "synthetic"},
        "segments": [{"kind": "straight", "name": "h", "node_a": "supply", "node_b": "return",
                      "heater": True, "geometry": {"length_um": 100, "width_um": 1}}],
        "drive": {"supply_node": "supply", "return_node": "return", "voltage_v": 2,
                  "voltage_definition": "rms_across_terminals"}})
    assert result["total_power_mw"] == 40
    assert result["material"]["layers_nm"] == {"test": 100}
    assert result["voltage_definition"] == "rms_across_terminals"


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(value)
                              for name, value in sorted(globals().items())
                              if name.startswith("test_") and callable(value))


if __name__ == "__main__":
    unittest.main()
