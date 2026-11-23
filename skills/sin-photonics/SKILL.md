---
name: sin-photonics
description: Computes SiN ring–straight-bus retained-channel coupling and coherent circular bends/routes using isolated COMSOL modes and built-in reference300-v1 dispersion. Use for geometry changes, neff/ng/FSR, channel Qc, bend transmission or their experimental comparisons. Do not use for GDS editing, arbitrary materials, full-device 3D scattering, roughness inference or general literature summaries.
metadata:
  version: "1.0"
  skill-author: "A426 Research Workbench"
---

# SiN photonics

Use the maintained `a426-sin-photonics` program, not historical task scripts. The program has independent `ring-bus` and `bends`/`routes` commands; they share material, modes, sampling, normalization and propagation code. Algorithm source belongs to `research/sin-photonics` in its maintenance repository. Installed Skill files are instructions and a thin launcher only.

## Select the calculation

- **ring-bus:** circular ring and tangent straight bus; independent FEM modes, neff/ng/FSR, complex retained-mode coupling and per-channel / total Qc. A wider bus may retain TE1 explicitly. Do not silently substitute TE0 if a requested mode cannot be identified.
- **bends/routes:** straight sections and signed circular arcs; target-basis Gram projection and coherent complex propagation. Return original-mode coefficient power, conversion coefficients, total retained power and insertion loss. Broadband interpolation needs phase-aligned solved anchors that bracket the requested range.
- **experimental comparison:** use the explicit accepted-design snapshot and the latest accepted measurement table. Preserve branch choices, exclusions, actual wavelengths and missing assignments. The theory must not choose the measured under/over-coupling branch.

Only reference300-v1 material is bundled. The nominal process is 300 nm SiN with 4 µm lower / 3 µm upper SiO₂, local silicon and PML. Users provide geometry, not dispersion coefficients. Thickness perturbations use the same process material and are not new material calibrations.

## Reproducible workflow

1. Read the target project's applicable rules and confirm its output boundary. In a maintenance/testing project, generate only inside permitted ignored test directories. External research assets remain read-only.
2. Locate an installed `sinphotonics` package or an explicitly supplied toolkit/reference package. Do not resolve missing inputs through an old absolute drive path. If using the thin launcher, provide `--toolkit` or `SIN_PHOTONICS_HOME`.
3. Read [references/operation.md](references/operation.md). Copy the appropriate example into the current task, edit the structure, and declare bottom/mid/top width **and gap** reference. A reference mode library can only be used when its cross section, wavelength, width, radius and requested branch match. A geometry change normally needs new COMSOL solves.
4. Run the relevant command with an explicit new output directory. For solves, use `--comsol-bin` or `COMSOL_BIN` (or a detected executable). Similar cases share a native sweep model per straight/bent cross-section family. No per-wavelength MPH loop. The runtime writes direct numeric NPZ, scalar CSV and text logs.
5. Inspect `result.json`, warnings and mode/branch diagnostics before interpreting curves. Read [references/physics-boundaries.md](references/physics-boundaries.md) for normalization, Q definitions and failure interpretation. Keep failed TM points diagnostic. Do not relabel a threshold as an absolute accuracy bound.
6. Deliver the self-contained, figure-first HTML, CSV, complex NPZ, configuration and model status. Use scientific-plotting for the report; the portable bundle contains a frozen renderer dependency. Do not add PNG/SVG copies or browser aesthetic checks unless requested.

## Verification and stopping conditions

- Check mode identification (polarization, nodes, confinement, light line), phase continuity, passive Im(neff), coordinate/weight metadata and target Gram conditioning. Ambiguous or missing modes require a refined search or explicitly reduced retained basis, not a fabricated branch.
- Qc screening combines retained exchange, integration-domain discrepancy and numerical evolution balance. Numerical conservation does not validate omitted radiation or the independent-mode approximation.
- A reference regression checks TE coupling, two bus channels, the failed TM case, coherent R40 route power and an independent 1555 nm anchor. A changed structure must also be run without the historical library.
- Label MPH state from readback evidence. Historical bend backups were cleared with `clearSolutionData()`; their exported NPZ remains usable, but they have no native solution. A display geometry is not a joint 3D coupled-field solve.
- Material absorption is zero. Geometry leakage Q is not measured intrinsic Q. If the task requires roughness, true backscatter, arbitrary curvature/materials or strong coupling validation, identify the missing physical capability instead of claiming that this workflow covers it.

## Completion

Report the actual command, tool version, output location, model state, reference checks and unresolved limitations. Keep original historical code/models frozen. Changes to the reusable algorithm or this Skill are made in the maintenance repository and tested before installation; a production analysis does not authorize editing external records or the installed source.
