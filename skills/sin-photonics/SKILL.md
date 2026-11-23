---
name: sin-photonics
description: Computes SiN ring–straight-bus retained-channel coupling and coherent circular bends/routes using isolated COMSOL modes and built-in reference300-v1 dispersion. Use for geometry changes, neff/ng/FSR, channel Qc, bend transmission or their experimental comparisons. Do not use for GDS editing, arbitrary materials, full-device 3D scattering, roughness inference or general literature summaries.
metadata:
  version: "1.1"
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
4. For geometry scans, first inspect `ring-bus --plan`; `scan` arrays form a Cartesian product and share deduplicated wavelength±2 nm anchors. Review native/coupling case counts before explicitly raising a budget. Run with an explicit new output directory. For solves, use `--comsol-bin` or `COMSOL_BIN` (or a detected executable). Similar cases share one native sweep MPH per family. The runtime writes numeric NPZ, scalar CSV and exact model/study/dataset/outer/eigenmode identities, including derivative anchors.
5. Inspect `result.json`, warnings and mode/branch diagnostics before interpreting curves. Read [references/physics-boundaries.md](references/physics-boundaries.md) for normalization, Q definitions and failure interpretation. Keep failed TM points diagnostic. Do not relabel a threshold as an absolute accuracy bound.
6. Deliver the self-contained, figure-first HTML, CSV, complex NPZ, configuration and model status. Link the portable package's `model-and-equations.html` when the user needs model/formula explanation; see [references/operation.md](references/operation.md) to regenerate it. Use scientific-plotting for report charts; the bundle contains a frozen renderer. Do not add PNG/SVG copies or browser aesthetic checks unless requested.

## Verification and stopping conditions

- Check mode identification (polarization, nodes, confinement, light line), phase continuity, passive Im(neff), coordinate/weight metadata and target Gram conditioning. Ambiguous or missing modes require a refined search or explicitly reduced retained basis, not a fabricated branch.
- Qc screening combines independent longitudinal-window convergence, sampling support, retained exchange, two-domain discrepancy and evolution balance. Inspect the expansion history and absolute envelope tails, not only zero-filled endpoint values. Near cancellation uses mixed absolute/relative tolerances. Automatic initial windows adapt to the local radius limit; an explicit initial value must leave enough expansions for the required consecutive passes. A stable or domain-consistent Qc alone cannot qualify the result.
- A ring-bus scan records a missing branch per geometry and continues independent cases. Any partial retained-basis result remains diagnostic with the missing channel null; never substitute TE0 for TE1. Bend/route basis construction still fails if a requested mode is unavailable.
- A reference regression checks TE coupling, two bus channels, the failed TM case, coherent R40 route power and an independent 1555 nm anchor. A changed structure must also be run without the historical library.
- Label MPH state from readback evidence. Historical bend backups were cleared with `clearSolutionData()`; their exported NPZ remains usable, but they have no native solution. A display geometry is not a joint 3D coupled-field solve.
- Material absorption is zero. Geometry leakage Q is not measured intrinsic Q. If the task requires roughness, true backscatter, arbitrary curvature/materials or strong coupling validation, identify the missing physical capability instead of claiming that this workflow covers it.

## Completion

Report the actual command, tool version, output location, model state, reference checks and unresolved limitations. Keep original historical code/models frozen. Changes to the reusable algorithm or this Skill are made in the maintenance repository and tested before installation; a production analysis does not authorize editing external records or the installed source.
