# 300 nm SiN ring coupling and circular routes

The maintained program for isolated COMSOL modes, ring–straight-bus coupling and coherent circular-arc routes. Version **1.1.0**. Algorithm source is here; `skills/sin-photonics` contains the assistant workflow and a thin launcher. Historical task scripts are frozen provenance, never runtime dependencies.

The portable distribution contains a standalone Chinese [model and equations guide](../model-and-equations.html) with embedded semantic SVG, material coefficients and formulas mapped to code. In a source checkout, generate it with `python scripts/build_guide.py --output <allowed-output>/model-and-equations.html`; its maintained template is [docs/model-and-equations.html.in](docs/model-and-equations.html.in).

## Version 1.1 changes

- Independent longitudinal convergence expands the half-window and compares both-domain weak complex amplitudes, finite output amplitudes, powers and outer-envelope tails. Default tolerances are 5e−4 relative amplitude, 1e−7 absolute amplitude, 1e−10 absolute power, and 1e−3 relative envelope tail. Two consecutive passes are required. Pre-zero-fill edge-field diagnostics reject unsupported truncation. Two-domain agreement alone cannot qualify a result.
- Omit `integration.extent_um` for radius-aware initialization: keep30 µm when it leaves enough expansions, otherwise use Lmax/growth^consecutive_passes, with Lmax=min(configured maximum, just below 0.8R). Explicit initial values must leave enough expansions; defaults do not make R40 or smaller supported radii structurally impossible. The complete history/thresholds live under each result's `window`. Self-phase uses a common center-referenced gauge across windows. These checks do not establish mesh/PML convergence or physical model accuracy.
- `scan` arrays `ring_widths_um`, `bus_widths_um`, `ring_radii_um`, `wavelengths_nm` form a Cartesian product; unspecified axes use scalar values. First run `ring-bus --config examples/ring-scan-small.json --plan`. Default execution budgets are 32 native channel/parameter cases and 128 coupling cases; raise `--max-native-cases` / `--max-coupling-cases` deliberately after reviewing the plan.
- Native ring/bus families deduplicate widths/radii and the union of λ±2 nm anchors. Gap never triggers FEM. Every case and derivative stencil links to model/study/dataset/outer/eigenmode identities in `native-mode-map.json` and family `native-map.csv`. One absent TE1 becomes a per-case diagnostic/null, without replacing it or stopping other geometries.
- The new native representative scan has 18 mode cases in two solved MPH files and 16 coupling outputs: ring widths1.2/1.3, bus widths1.1/1.2, R57.932443/60, λ1550, gaps1.1/1.2. `VerifySweep.java` reopens all saved parameter/eigenmode identities; `tests/sin-photonics/verify_v11.py` verifies final-code replay, window limits and missing-channel isolation.

The frozen scalar reference at gap1.2 changes from Qc=3.5392679 M at an insufficient15 µm half-window to approximately3.456625 M after expansion. R40's historical field has an edge ratio≈2.27e−4 and remains sampling-domain diagnostic; reachable expansion is not an automatic pass. A full Chinese explanation and limitations are in the guide.

The only material preset is **reference300-v1**. Its complete SiN/SiO₂ Sellmeier formulas are in `sinphotonics/materials.json`; both Python and COMSOL consume this file. At 1550 nm, nSiN=1.996351530914008 and nSiO₂=1.444266379413012. The supported workflow range is 1530–1570 nm. No user-supplied dispersion table is required. Thickness perturbations retain this same process material, not a different fitted process.

## Run

Python ≥3.11 with NumPy ≥2, SciPy ≥1.14 and jsonschema ≥4.20. Tested on Python 3.13, NumPy 2.4.6, SciPy 1.18.0 and COMSOL 6.1.0.252 on Windows. COMSOL needs a valid license and the electromagnetic mode solver. The native launcher currently targets Windows executables; other platforms are not verified.

From this toolkit directory:

```powershell
python -m sinphotonics ring-bus --config examples/ring-reference.json --output <new-output> --comsol-bin <COMSOL-bin-win64>
python -m sinphotonics bends --config examples/bend-single.json --output <new-output> --comsol-bin <COMSOL-bin-win64>
```

Or install the program: `python -m pip install <toolkit-directory>` and use `sin-photonics`. COMSOL discovery priority is `--comsol-bin`, `COMSOL_BIN`, then PATH. Python is the caller's interpreter, not a hardcoded executable. Paths and outputs are explicit; existing output directories are rejected.

The share package includes a portable field library and a frozen scientific-plotting runtime. From its root:

```powershell
$env:PYTHONPATH = (Resolve-Path toolkit).Path
python -m sinphotonics ring-bus --config toolkit/examples/ring-reference.json --library modes --output replay-ring
python -m sinphotonics ring-bus --config toolkit/examples/ring-two-channels.json --library modes --output replay-two-channels
python -m sinphotonics bends --config toolkit/examples/route-r40-reference.json --library modes --output replay-route
python toolkit/scripts/package_manifest.py verify .
```

Do not put `--library` on a changed-geometry run unless that exact configuration exists in it. Cross section, material, widths, radii, wavelengths, branches and hashes are checked. Use `examples/ring-modified.json` without `--library` to solve a genuinely different structure. `routes` is an alias for `bends`. A scalar circular bend and a series of signed arcs/straights use the same implementation.

Source-tree report generation discovers an installed scientific-plotting Skill or `SIN_PLOTTING_ROOT`. Portable delivery discovers its sibling `plotting-runtime`. A pip-only installation can set `SIN_PLOTTING_ROOT` to that directory. This dependency is copied only into the ignored distribution, with hashes; its maintained source remains in scientific-plotting. No second plotting source is maintained here.

## Configuration and outputs

`sinphotonics/config.schema.json` defines units, bounds and accepted keys. Examples are deliberately readable JSON. `cross_section.size_reference` applies to **both widths and gap**: bottom/mid/top. The radius is always the ring centerline. For h and θ, bottom width=mid width+h cotθ; bottom gap=mid gap−h cotθ; top corrections are twice those values. Geometry, interpolation sampling and integration weights share the same parameters.

Default cross section: 300 nm SiN, 86° wall, 4 µm lower / 3 µm upper SiO₂, a truncated local silicon substrate (n=3.48), upper air and exterior PML. The whole 500 µm substrate is not drawn. Material absorption is zero. Core mesh maximum=35 nm×mesh_scale (default .7). Physical transverse window is x=±8 µm, y=−5.5…4.5 µm; PML outer edges ±10 µm, −7.5…6.5 µm. The integration window is x=±7.8 µm. New geometries still need problem-specific mesh/window/PML convergence checks before quantitative design commitment.

Eigenvalue search uses the frozen run03 width-dependent TE seeds (not material parameters or predicted output indices). Missing ring-bus branches are recorded per geometry and partial-basis results stay diagnostic; bends/routes require all requested modes. For an inspected shifted branch, optional `mode_search` accepts `{"eigenmodes":8,"shifts":{"TE1":1.54}}`; this changes the search location, not the result. No automatic branch substitution occurs. `examples/bend-two-mode.json` exercises TE0↔TE1 conversion in a 2 µm route with opposite signed R40 bends.

Each result includes:

- `report.html`: self-contained semantic SVG, structure first, warnings and collapsed numeric table; no duplicate PNG or SVG export.
- `result.json`, `configuration.json`, scalar `coupling.csv` or `route.csv`.
- `complex_coupling.npz` or `route_complex.npz`: complex amplitudes and kernels / spectral anchor matrices.
- On fresh solves: one MPH per straight or bent mode family, all similar width/wavelength/radius cases in native parameter sweeps; direct raw numeric NPZ, manifest, text logs and a local runtime directory.

Native raw arrays: `info` rows are Re(neff), Im(neff), core fraction, TE fraction, nSiN, nSiO₂, bottom width/µm, wavelength/nm, radius/µm. `line_j`, `full_j`, `core_j` interleave real/imaginary components. Full fields are E then H; Cartesian x/y/z or cylindrical r/z/φ. Coordinates and quadrature cell weights are metres. `cross_section` records thickness/µm, wall/deg, lower/upper oxide/µm. These are interpolation samples, not native FEM nodes. Each file corresponds to one native outer solution and retains candidate identification information. Logs never contain arrays.

## Reference and verification

Main design: ring/bus bottom width 1.2 µm, R=57.932443 µm, reference ring index 7, FSR≈420.2105457 GHz, array radius increment≈9.193684 nm. Accepted Chip2 geometry is run04; run02 is the optical baseline and run03 is retired. The coupling historical radius differs only by 0.000000025 µm from the rounded accepted reference.

Earlier v1.0 reference checks (fixed-window historical evidence, supplemented by v1.1 convergence above):

| Check | Actual result |
|---|---|
| Four TE reference gaps 1.0/1.1/1.2/1.3 µm | Qc≈1.04131/1.89913/3.45663/6.27617 M; maximum difference from the archived scan 0.0346% |
| 2 µm ring and 2 µm bus, gap .8 µm | Qc,TE0≈5.95098 M; Qc,TE1≈1.56237 M; retained total≈1.23748 M |
| New native reference solve | ring neff=1.596376323; ng=1.959981849; FSR=420.210541 GHz; gap1.2 Qc≈3.45602 M |
| Failed TM at gap1.2 | domain amplitude discrepancy≈21.33%; ideal geometry Q≈29195; diagnostic status retained; all 33 archived failures preserved |
| Historical 12×R40 route at1550 | TE total=0.8755899912; TM total=0.0275325830 |
| Route arbitrary phase-gauge check | maximum power difference <9×10⁻¹⁵ |
| Independent1555 anchor vs interpolation | absolute TE/TM power errors 2.17×10⁻⁸ / −7.22×10⁻⁹ |
| Changed structure with no library | h310 nm, wall87°, mid widths1.15/1.1 µm, R60, mid gap1.2→bottom1.183754 µm; Qc≈2.41101 M |
| Fresh single90° R40 solve | TE total≈0.9889920; TM total≈0.7414418 |
| Fresh 2 µm TE0/TE1 route | Two opposite R40 arcs +170 µm straight: TE0-input retained power≈0.9956963; TE1 coefficient power≈0.00438573 |

Eleven synthetic tests check material dispersion, variable-thickness area, analytic complex evolution, Q limits, passive propagation, invalid corners, small-radius window reachability, finite-support rejection, mixed absolute tolerances, spectral deduplication and native SVG markup in HTML. `tests/sin-photonics/verify_reference.py` checks historical real-field regressions; `verify_v11.py` checks the added convergence/scan behavior. Real data, generated models, figures and test results remain ignored under `tests/sin-photonics/local/`.

The model reference pair is newly solved at1548/1550/1552 nm and loadCopy-readback verified with nonempty solver data. Open it in COMSOL6.1; select the study/parameter/eigenmode in the `Mode field` plot. The compact bend/straight templates have TE0/TM0 studies at1550 nm, cleared solution data and cleared generated mesh, with mesh settings, geometry/material/physics/studies retained. Rebuild mesh and run a study to populate them. They are isolated cross-section models, not a combined 3D coupling solve.

## Physical limits

Propagation convention is exp(+iωt−iβs); passive Im(neff)<0. Positive gain is rejected rather than hidden by abs(). Mode identification uses core polarization, confinement, light line and node count. The group-index stencil uses wavelength±2 nm with field-line overlap tracking. Broad degenerate/hybrid regions require additional mode tracking and are rejected when detected.

Ring coupling keeps the complex spatial overlap, finite Hermitian star evolution, per-channel output Kj, Ktot=ΣKj, Trt=2πRng/c, Qc,total=ωTrt/[−ln(1−Ktot)], and Qc,j=Qc,total Ktot/Kj. Zero coupling gives infinity (null in JSON). Retained-channel total Q is not loaded Q. Screening requires longitudinal/support checks above plus Ktot≤1%, two-domain amplitude difference≤1e−7+2% of the larger amplitude, and balance error≤1e−5. They are not absolute physical accuracy guarantees. The independent nonorthogonal domain integrals need not agree exactly. Bus-basis Gram deviation is checked; a general nonorthogonal coupled-mode solver is not implemented. `diagonal_phase` adds fixed-mode self-phase only, not mode reshaping.

Route interfaces solve target G⁻¹C, retain complex amplitude and evaluate a†Ga. Coefficient powers |aj|² need not sum to total in a nonorthogonal basis. The broadband path aligns mode phases, uses cubic interpolation of real indices and interface/Gram matrices, log-PCHIP of negative imaginary magnitudes with a declared 10⁻¹⁶ floor, and forbids extrapolation. The output at every wavelength is coherent. It does not resolve the full reflection/radiation continuum or radiation recapture. Unretained power is not an exact radiation-loss calculation. Straight sections and circular arcs are implemented; arbitrary curvature/Euler bends are not.

The 12-bend reference is the old500 µm-row-spacing cavity-free route, not the current750 µm-row-spacing device with cavities and metal. No full-chip validation is implied. Roughness/backscatter, arbitrary materials, strong coupling and physically validated leaky-TM Qc are outside this implementation. Numerical conservation cannot validate omitted channels. Geometry leakage Q is not experimental intrinsic Q.

## Experiment

`scripts/compare_experiment.py --reference <package> --output <new-output>` compares every Chip2 row from the latest Nov20 `array-mu0.csv` with accepted run04 design parameters. It preserves inclusion flags, fit model, under/over-coupling note, cavity assignment and actual μ=0 wavelength offset. It does not refit or choose branches from theory. Arithmetic means and sample standard deviations use the supplied flags.

The generated local report shows every measured die, including disagreements; real experimental values and tables remain outside Git. An included row with no cavity ID remains explicitly unassigned, is compared only when its die has one unique gap, and is not assigned a ring radius. Its source inclusion flag is preserved and the missing assignment is visible in CSV. Missing μ=0 rows remain in the all-rows table and follow the source exclusion flag.

86° is a design assumption, not independently SEM-confirmed. ng inferred from FSR is not an independent check. Fitted Q0 may include unobserved-channel loss. End-to-end IL cannot isolate bends; the old≈1.494434 dB estimate also used a1.1 µm taper approximation for1.2 µm and the old cavity-free route.

## Rebuild, export and seal a share package

All input paths are explicit. In Workbench, use new ignored test output directories. The source library remains read-only.

1. Run the reference ring config without `--library`; its output has `ring/` and `bus/` native folders.
2. Run `bend-single.json` without `--library`, then `scripts/export_templates.py --bend-model <bend/models/bend_modes.mph> --straight-model <straight/models/straight_modes.mph> --output <new-template-dir> --comsol-bin <bin>`. This uses loadCopy, verifies source hashes unchanged, and reads back cleared solutions.
3. Run `scripts/build_reference.py --source-library <read-only-library> --native-reference <reference-run> --templates <template-dir> --plotting-root <scientific-plotting-skill> --skill-source <sin-photonics-skill> --output <new-package>`.
4. Generate the experiment report and selected replays into the new package or another allowed test directory. Include relevant scalar verification summaries. Seal with `scripts/package_manifest.py seal <package> --zip <new-zip-outside-package>`; verify with the corresponding `verify` action. ZIP CRC and SHA256 complement, not replace, native readback.

The builder restricts real arrays to necessary reference cases and copies only the representative native models/templates, never the complete historical model collection. The package is a local distribution; models, experiments, report outputs and frozen renderer copies are excluded from Git. Checksums permit redistributing the package without the historical E-drive layout. Scientific SVG integrity is checked without PNG/SVG duplicates or browser screenshot loops; scientific and visual interpretation remains subject to user review.

## Provenance and maintenance

Frozen sources, relative to the explicit research library root:

- `research/sin-ring-bus-coupling/scripts/run-02/{analyze_modes,coupler_scan,launch_native}.py`: vector overlap, normalization and native launcher origin.
- `research/sin-ring-bus-coupling/scripts/run-03/{NativeModes.java,sweep_coupling.py}`: TE0/TE1 scan and star evolution.
- `research/sin-ring-bus-coupling/scripts/run-05/diagonal_phase_qc.py`: fixed-mode self-phase option.
- `research/sin-ring-bus-coupling/scripts/run-08/{NativeModes.java,analyze.py}` and raw/processed run03/run08: reference300 dispersion, native sweeps and negative TM evidence.
- `research/chip2-simulation-backup/2026-10-07/bend-filter/scripts/{analyze,spectrum}.py` and raw/processed run01: signed interfaces, Gram projection and coherent spectrum. Its root backup README overrides old claims about stored native solutions.
- `outputs/流片/2026-10-nine-chip-array/chip_02/accepted/{parameters,provenance}.json`: accepted geometry.
- `summaries/weekly/2026-11-09_to_2026-11-20/assets/nov20/array-mu0.csv`: latest local experiment table.

`sources.json` in a built package records source names, versions and SHA256. The historical source files were read only. No migration note was written into the external library; its owner can add a link to this toolkit and the delivery commit in a library-scoped task.
