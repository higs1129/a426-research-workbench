# Electrode resistance and heater power

Read when generating electrode resistance labels, changing leads, or converting a local heater response to a voltage coefficient. Use `scripts/electrode_resistance.py` for deterministic arithmetic. This is a cold-resistance model, not a thermal solver.

## Inputs and provenance

Specify sheet resistance `Rs` in ohm/square, each material thickness in nm, and separate sources for the sheet resistance and thickness. Measured/fitted sheet resistance already includes its film stack; do not divide by thickness a second time. If deriving a stack value from conductivity, parallel film conductance is `Gsheet = sum(sigma_i * t_i)` with thickness in metres and `Rs = 1/Gsheet`.

Historical evidence: the research task `electrode-heating-air-water`, README section 4 and `run-06-resistance-design`, fitted `Rs = 0.842567 ohm/square` for Ti 10 nm / Pt 200 nm. It uses eight group means from cold two-probe measurements on 4/8 um electrode geometries, with FEM geometric square counts and a zero-intercept common fit (group RMSE 23.10 ohm). This is a process-specific fitted value, not a universal Pt constant or an independently measured contact resistance. The alternative fitted intercept was not evidence of a contact resistance. Keep it explicit when deliberately reusing that profile; scripts have no default Rs or thickness.

The current source geometry examples are `2026-10-nine-chip-array/chip_09/big-membrane-die-preview/estimate_phase.py` and `chip_07/layout-05/electrodes.py`. They use the formulas below; the former records Ti10/Pt200 and cold resistance, the latter preserves separate heater and lead contributions. These are source identifiers for read-only evidence, not paths to execute or migrate. Regenerate labels from the current geometry and current network, not from an old chip's reported resistance.

## Geometry formulas and limits

Use consistent length units within each formula. In the script all lengths are um and angles are radians.

- Straight strip: `R = Rs * L/w`.
- Linear taper: `R = Rs * L * ln(w2/w1)/(w2-w1)`. For equal widths use `Rs * L/w`; evaluate near equality with `log1p`. This is a one-dimensional width integral and ignores two-dimensional current crowding.
- Annular arc: `R = Rs * theta / ln(ro/ri)`, where `ri > 0`, `ro > ri`. Derivation: concentric radial strips conduct in parallel, `dG = dr/(Rs * theta * r)`. It assumes equipotential radial end faces, homogeneous film and insulating circular edges. The thin-strip limit is `Rs * theta * r_center/w`. A full 2 pi entry describes a cut annulus with two terminals, not an uncut ring with ambiguous contacts.
- Sum series resistances only when they carry the same current. Parallel paths share voltage; shared leads and bridge circuits require their actual node connectivity. Do not sum every polygon as if all metal were one series path.

Avoid counting pad overlap twice as exposed lead length. Sharp joints, corners, pad spreading and local width changes can require an explicit correction or an electrical FEM check. The analytic formulas do not validate physical polygon connectivity.

## Network power and thermal conversion

The script solves the declared node network and reports each branch's `I`, `P = I^2 R`, total power and `eta = P_heater/P_total`. It rejects duplicated element names, invalid resistance, missing terminal nodes, self-loops, disconnected subcircuits and failed power balance. Separate independent two-pad circuits are separate network solves; do not invent a common return node. A connected balanced bridge may legitimately have a zero-current branch.

Voltage is explicitly DC across the named terminals or sinusoidal RMS across them. Instrument source voltage, voltage across just the heater, pad-to-pad voltage, and peak AC amplitude are not interchangeable. Peak amplitude must first be converted to RMS when mean power is intended. For AC thermal response, RMS power alone does not establish modulation bandwidth or temperature dynamics.

For a series heater `Rh` and total resistance `Rtotal`, pad voltage V gives:

```text
Ptotal[mW] = 1000 * V^2 / Rtotal
Pheater[mW] = 1000 * V^2 * Rh / Rtotal^2
eta = Rh / Rtotal
beta[GHz/V^2] = 1000 * S_local[GHz/mW] * Rh / Rtotal^2
```

For a general network, calculate heater power from the solved branch current before multiplying by `S_local`. A coefficient normalized to heater power must not be multiplied by total pad power. `thermal_proxy` accepts signed coefficients for explicitly identified heater branches contributing to one optical observable, requires their source and reports omitted heater branches. The caller must justify coefficient transfer, matching geometry/environment/mode and linear superposition; different optical outputs must be reported separately. A local coefficient or its electrical conversion does not become a full-structure thermal tuning prediction. Lead heating, thermal cross-talk, spatially nonuniform heating and reference-arm heating remain unmodeled unless independently included in the underlying thermal model.

Not included by default: contact resistance, pad current spreading, metal R(T), temperature-dependent thermal/optical coefficients, new three-dimensional heat flow, thermo-mechanical phase and experimental calibration uncertainty. If a known contact resistance matters, include it explicitly as a sourced network element through the Python API; the geometry-only JSON frontend does not silently invent it.

## Design priorities and pad groups

Reduce ordinary supply-lead resistance first, subject to clearances and routing. Do not blindly widen the active heater: its width and placement set the thermal target and current distribution. Distinguish array cavities and single cavities. Single-cavity electrode pad groups are usually at different heights; no universal same-height default is valid. Keep pad size and within-group probe spacing fixed to the accepted component/profile. Moving a group preserves its internal geometry; group anchors and device-to-device heights are separate design variables. Historical chip offsets are evidence for their own profile, not global defaults.

## Minimal explicit JSON input

The values below are synthetic; replace material and geometry with sourced run data. Run `python scripts/electrode_resistance.py input.json`; the report is JSON on stdout and invalid specifications exit with code 2. No files or GDS are modified.

```json
{
  "material": {
    "sheet_resistance_ohm_per_square": 1.0,
    "layers_nm": {"synthetic_metal": 100},
    "sheet_resistance_source": "synthetic example, replace for production",
    "thickness_source": "synthetic example, replace for production"
  },
  "segments": [
    {"name": "heater", "node_a": "pad_a", "node_b": "join", "heater": true,
     "kind": "straight", "geometry": {"length_um": 100, "width_um": 1}},
    {"name": "lead", "node_a": "join", "node_b": "pad_b", "heater": false,
     "kind": "linear_taper", "geometry": {"length_um": 100, "width1_um": 1, "width2_um": 4}}
  ],
  "drive": {"supply_node": "pad_a", "return_node": "pad_b", "voltage_v": 1,
            "voltage_definition": "dc_across_terminals"},
  "thermal": {"coefficients_ghz_per_mw": {"heater": 2}, "source": "synthetic same-observable example"}
}
```

For an annular arc, `geometry` takes `inner_radius_um`, `outer_radius_um`, `angle_rad`. For parallel/branched routes, reuse the actual common node names; every segment name remains unique. Archive the input alongside the output so resistance labels, parameter tables and mask geometry retain the same provenance.

Regression checks run without external packages: `python -B -m unittest discover -s skills/photonic-gds-layout/tests -p test_electrode_resistance.py -v` from the repository root. The same test functions also run under pytest.
