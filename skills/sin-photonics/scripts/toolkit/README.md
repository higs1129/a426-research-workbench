# SiN photonics implementation

This is the sole maintained algorithm source inside the self-contained [Skill](../../README.md), version2.0.0. Use `scripts/run.py` from the Skill root so the Python package and its bundled renderer are resolved together. An isolated pip install of this subdirectory is not the complete Skill installation.

- `sinphotonics/native/NativeModes.java`: Cartesian/axisymmetric COMSOL geometry, materials, meshing, PML, native sweeps and NPZ export.
- `sinphotonics/materials.json`: sole300 nm process dispersion source shared by Python and COMSOL.
- `geometry.py`, `modes.py`: explicit cross sections, sampling weights, mode identification, normalization and group index.
- `coupling.py`, `scan.py`: complex overlap, finite evolution, independent window/support diagnostics and deduplicated geometry scans.
- `routes.py`: target Gram projection, phase-aligned interpolation and coherent route propagation.
- `report.py`: HTML plus the bundled semantic SVG renderer.
- `docs/model-and-equations.html.in` and `scripts/build_guide.py`: deterministic standalone model explanation.

Physics conventions and limitations are in the Skill's [physical reference](../../references/physics-boundaries.md). Preserved derivation origins are frozen `sin-ring-bus-coupling` run02/run03/run05/run08 and `chip2-simulation-backup/2026-10-07/bend-filter` run01. These describe provenance; historical source files are not imported at runtime.

The numerical algorithms are unchanged by the2.0 packaging migration. The1.1 fixed-field regressions remain applicable: reference gap1.2 converges to Qc≈3.456625 M, fixed-window self-phase regression error<1e−8, and the archived R40 route's1550 nm retained powers are0.8755899911763/0.0275325830381 for TE/TM. These are numerical regression references, not general physical error bounds. R40 ring-bus field-support failure remains diagnostic.

Optional helpers `scripts/compare_experiment.py` and `scripts/export_templates.py` take explicit external inputs and outputs; they contain no personal data. Read their CLI help before use. Generated reports, fields, models and caches stay outside this source tree.
