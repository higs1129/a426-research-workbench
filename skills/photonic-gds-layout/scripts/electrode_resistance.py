"""Analytic cold electrode resistance and DC/RMS network power; no thermal solve.

Run ``python electrode_resistance.py input.json`` for a JSON report on stdout.
Lengths in each formula use micrometres, thickness metadata uses nanometres.
No process/material values are implicit. See references/electrode-resistance.md.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path


def positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


@dataclass(frozen=True)
class Material:
    sheet_resistance_ohm_per_square: float
    layers_nm: dict[str, float]
    sheet_resistance_source: str
    thickness_source: str

    def __post_init__(self):
        positive(self.sheet_resistance_ohm_per_square, "sheet resistance")
        if not self.layers_nm or not self.sheet_resistance_source.strip() or not self.thickness_source.strip():
            raise ValueError("material layers, sheet resistance source and thickness source are required")
        for name, thickness in self.layers_nm.items():
            if not name.strip():
                raise ValueError("material name is required")
            positive(thickness, "thickness_nm")


def straight(material: Material, length_um: float, width_um: float) -> float:
    return material.sheet_resistance_ohm_per_square * positive(length_um, "length_um") / positive(width_um, "width_um")


def linear_taper(material: Material, length_um: float, width1_um: float, width2_um: float) -> float:
    """1-D integral Rs * integral(ds/w(s)); ignores 2-D current crowding."""
    length = positive(length_um, "length_um")
    lo, hi = sorted((positive(width1_um, "width1_um"), positive(width2_um, "width2_um")))
    x = (hi - lo) / lo
    factor = 1.0 if x == 0 else math.log1p(x) / x
    return material.sheet_resistance_ohm_per_square * length / lo * factor


def annular_arc(material: Material, inner_radius_um: float, outer_radius_um: float, angle_rad: float) -> float:
    """Ideal equipotential radial end faces; insulating inner/outer arcs."""
    ri, ro = positive(inner_radius_um, "inner_radius_um"), positive(outer_radius_um, "outer_radius_um")
    theta = positive(angle_rad, "angle_rad")
    if ro <= ri or theta > math.tau:
        raise ValueError("arc requires outer > inner radius and 0 < angle_rad <= 2*pi")
    return material.sheet_resistance_ohm_per_square * theta / math.log1p((ro - ri) / ri)


@dataclass(frozen=True)
class Resistor:
    name: str
    node_a: str
    node_b: str
    resistance_ohm: float
    heater: bool
    source: str

    def __post_init__(self):
        if not all(isinstance(s, str) and s.strip() for s in (self.name, self.node_a, self.node_b, self.source)):
            raise ValueError("resistor name, node names and source are required")
        if self.node_a == self.node_b:
            raise ValueError("self-loop resistor is not a physical branch")
        if not isinstance(self.heater, bool):
            raise ValueError("heater must be an explicit boolean")
        positive(self.resistance_ohm, "resistance_ohm")


def _linear_solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Partial pivoting for the small declared resistor networks used here."""
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(a[i][col]))
        if a[pivot][col] == 0:
            raise ValueError("singular network; check disconnected nodes")
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(col + 1, n):
            factor = a[row][col] / a[col][col]
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    result = [0.0] * n
    for i in range(n - 1, -1, -1):
        result[i] = (a[i][n] - sum(a[i][j] * result[j] for j in range(i + 1, n))) / a[i][i]
    return result


def solve_network(resistors: list[Resistor], supply_node: str, return_node: str,
                  voltage_v: float, voltage_definition: str) -> dict:
    """voltage_v is measured across named terminals, DC or sinusoidal RMS.

    Shared leads, parallel arms and bridge branches are solved by nodal analysis.
    Peak or source-instrument voltage is intentionally not inferred.
    """
    positive(voltage_v, "voltage_v")
    if voltage_definition not in {"dc_across_terminals", "rms_across_terminals"}:
        raise ValueError("voltage_definition must explicitly be DC or RMS across terminals")
    if not resistors or len({r.name for r in resistors}) != len(resistors):
        raise ValueError("network must contain uniquely named resistors")
    nodes = {n for r in resistors for n in (r.node_a, r.node_b)}
    if supply_node == return_node or supply_node not in nodes or return_node not in nodes:
        raise ValueError("distinct supply and return nodes must exist in network")
    seen, todo = set(), [supply_node]
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        for r in resistors:
            if node in (r.node_a, r.node_b):
                todo.extend([r.node_a, r.node_b])
    if seen != nodes:
        raise ValueError("disconnected network or floating branch")
    unknown = sorted(nodes - {supply_node, return_node})
    indices = {node: i for i, node in enumerate(unknown)}
    potentials = {supply_node: voltage_v, return_node: 0.0}
    matrix = [[0.0] * len(unknown) for _ in unknown]
    rhs = [0.0] * len(unknown)
    for r in resistors:
        g = 1.0 / r.resistance_ohm
        for node, other in ((r.node_a, r.node_b), (r.node_b, r.node_a)):
            if node in indices:
                i = indices[node]
                matrix[i][i] += g
                if other in indices:
                    matrix[i][indices[other]] -= g
                else:
                    rhs[i] += g * potentials[other]
    potentials.update(zip(unknown, _linear_solve(matrix, rhs)))
    branches, input_current = {}, 0.0
    for r in resistors:
        dv = potentials[r.node_a] - potentials[r.node_b]
        current = dv / r.resistance_ohm
        branches[r.name] = {**asdict(r), "voltage_v": dv, "current_a": current,
                            "power_mw": 1000 * dv * current}
        if r.node_a == supply_node:
            input_current += current
        if r.node_b == supply_node:
            input_current -= current
    input_power = 1000 * voltage_v * input_current
    total = sum(b["power_mw"] for b in branches.values())
    if input_power <= 0 or not math.isfinite(total) or not math.isclose(total, input_power, rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError("network power balance failed; check resistance scales")
    heater_power = sum(b["power_mw"] for b in branches.values() if b["heater"])
    return {"supply_node": supply_node, "return_node": return_node,
            "voltage_v": voltage_v, "voltage_definition": voltage_definition,
            "equivalent_resistance_ohm": voltage_v / input_current,
            "input_current_a": input_current, "total_power_mw": total,
            "heater_power_mw": heater_power, "heater_power_fraction": heater_power / total,
            "node_potentials_v": potentials, "branches": branches}


def thermal_proxy(network: dict, coefficients_ghz_per_mw: dict[str, float], source: str) -> dict:
    """Signed local responses at ONE optical observable, per branch power.

    The caller must establish linear superposition and matching heater geometry.
    This conversion alone cannot certify full-device thermal tuning.
    """
    if not source.strip() or not coefficients_ghz_per_mw:
        raise ValueError("thermal coefficients and their source are required")
    shift = 0.0
    for name, coefficient in coefficients_ghz_per_mw.items():
        if name not in network["branches"] or not network["branches"][name]["heater"]:
            raise ValueError("thermal coefficient must refer to a declared heater branch")
        if isinstance(coefficient, bool) or not math.isfinite(coefficient):
            raise ValueError("thermal coefficient must be finite")
        shift += coefficient * network["branches"][name]["power_mw"]
    return {"status": "local-heater proxy; not a full-device thermal prediction",
            "coefficient_source": source, "coefficients_ghz_per_mw": coefficients_ghz_per_mw,
            "shift_ghz": shift, "beta_ghz_per_v2": shift / network["voltage_v"] ** 2,
            "voltage_definition": network["voltage_definition"],
            "unmodeled_heater_branches": [name for name, b in network["branches"].items()
                                            if b["heater"] and name not in coefficients_ghz_per_mw]}


def evaluate(spec: dict) -> dict:
    material = Material(**spec["material"])
    formulas = {"straight": straight, "linear_taper": linear_taper, "annular_arc": annular_arc}
    resistors = []
    for item in spec["segments"]:
        kind = item["kind"]
        if kind not in formulas:
            raise ValueError(f"unknown segment kind: {kind}")
        value = formulas[kind](material, **item["geometry"])
        resistors.append(Resistor(item["name"], item["node_a"], item["node_b"], value,
                                  item["heater"], f"analytic {kind}; {material.sheet_resistance_source}"))
    result = solve_network(resistors, **spec["drive"])
    result["material"] = asdict(material)
    result["model"] = "analytic cold resistance; ideal junctions; no contact/pad spreading or R(T)"
    if "thermal" in spec:
        result["thermal"] = thermal_proxy(result, **spec["thermal"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.input.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"invalid electrode specification: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
