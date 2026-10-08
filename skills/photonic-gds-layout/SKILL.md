---
name: photonic-gds-layout
description: Creates, modifies, migrates, and verifies photonic or microdevice GDS layouts through KLayout/klink from user sketches, KLayout selections, structured parameters, component ports, routing constraints, and clean-export requirements. Use for resonators, cavities, waveguides, couplers, Euler routes, arrays, chip facets, and legacy GDS migration. Do not use for fabrication records, simulation-only analysis, or decorative scientific illustrations.
metadata:
  version: "1.2"
  skill-author: "Personal Research Workflow"
---

# Photonic GDS Layout

## Purpose and boundaries

Turn a conceptual sketch, a live KLayout selection, or a legacy layout into a reproducible photonic GDS design with explicit parameters, reusable components, connected ports, verification evidence, and a clean export.

The Skill orchestrates design decisions and KLayout/klink operations. Reusable device geometry and production assets belong to the active layout project. This Skill carries the user's approved SiN conventions as a small overridable profile, separate from generic geometry helpers; it is not a universal foundry PDK. Treat legacy libraries and research records as read-only unless the current project explicitly owns them. Workbench Skill tests write only to this Skill's `tests/`, never back to research sources.

Live editing expects Python 3.10+, KLayout 0.30.x, and a version-matched klayout-klink client/plugin. Optional photonic routing uses gdsfactory 9.x.

## When to use

- Use for a new or revised resonator, cavity, bus waveguide, Euler route, taper, facet connection, array, mask cell, or GDS hierarchy.
- Use when the user sends a KLayout selection/ruler and refers to “this cavity,” “this area,” or “the route I just sent.”
- Use to migrate a stable legacy MATLAB/GDS device into a parameterized component with ports and verification.
- Do not use to record a completed fabrication run; use the fabrication-record workflow instead.
- Do not use when the intended output is only a plot, simulation, or illustrative diagram rather than layout geometry.

## Operating modes

Choose one mode before mutating a layout:

1. **New design** — start from a sketch and structured specification.
2. **Live edit** — inspect the active KLayout session and exact selection before changing it.
3. **Legacy migration** — inspect the source file/code read-only, extract geometry and conventions, then reproduce it in a test-owned project.

## Reproducible workflow

### 1. Preflight

Run `scripts/check_environment.ps1` when the task needs live KLayout. Confirm the KLayout desktop version, active klink session, client/plugin version handshake, writable project output root, and required Python capabilities.

Use a dedicated KLayout window or test-owned layout for initial generation. Never clear, close, or overwrite an ambiguous active tab.

### 2. Intake with useful defaults

Ask only for missing choices that change topology or fabrication output:

- unit structure and intended function;
- how units connect;
- chip-edge or facet interface;
- process/layer mapping;
- fixed versus swept parameters.

If a numerical detail is absent but a reversible test default is reasonable, prefill it, label it as an assumption, and continue. Do not require the user to fill a blank form from scratch.

For this user's SiN work, automatically read `references/sin-process-profile.md` and resolve `assets/sin-user-process.json`. Reuse confirmed choices across follow-ups. The profile distinguishes 500/1000 µm exposure groups, SiN versus UV layers, and single-cavity versus array pad components. Only SiN/optical text and writefields change datatype with field size. Source pad dimensions/spacing from an accepted component; separate group anchors may have different heights. Do not select a universal height from the latest chip.

### 3. Acquire design intent

- Use existing structured parameters and accepted geometry first. If missing conceptual topology needs a sketch, invite a daily-canvas drawing; read its Markdown/state/preview as read-only evidence.
- When exact geometry is provided via KLayout, resolve the durable `SEND` selection/ruler through klink. Request a selection only if the target is otherwise unresolved; do not infer precise coordinates from a screenshot.
- When both exist, the daily sketch defines topology and the KLayout selection defines coordinates and objects.

### 4. Build and validate the specification

Use `assets/design-spec.template.yaml` for the included microring/Euler reference case; other families extend the project specification with the same process/port/change-scope semantics. Prefill known values and mark unresolved fields. Read `references/design-spec-schema.md`. For the reference case run:

```powershell
python scripts/validate_design_spec.py path\to\design-spec.yaml
```

Resolve the specification once topology, layers, dimensions, sources and export target are coherent. Ask only for a consequential unresolved choice; prior explicit approval is sufficient. For a local edit record `change_scope`: editable items, preserved items, and dependent quantities to recompute. Protect unaffected layers and pad-group relations.

Use one scan table as the source for geometry, labels and manifests. Declare pair rotation (including whether 180°) and shared-slot ownership independently. For SiN the profile supplies a strict **three-point distance <0.1 nm**, with uniform curve stations; the manual says “around 0.1 nm” and the user's explicit rule supplies the strict upper bound. See the metric, quantization and source details in `references/design-spec-schema.md`.

### 5. Resolve components

For each unit, search in this order:

1. the active project component/toolbox library;
2. the indexed legacy implementation, read-only;
3. a new parameterized implementation.

Every reusable component must satisfy `references/component-port-contract.md`. Validate one unit's critical dimensions, origin, ports, layer set and bounding box before arraying or routing. Reuse an already accepted component/profile; do not repeatedly request approval for unchanged geometry.

### 6. Assemble and route

Place units hierarchically. Connect named ports rather than guessed polygon endpoints. Keep the cavity coupling segment straight when specified; use Euler bends for edge transitions when requested. Preserve explicit minimum radius, width, clearance, and keepout constraints.

Coordinate routes globally and try alternate paths. Prefer complete SiN cavities/bends, coupling regions and tapers within individual EBL fields, testing full-width geometry. Necessary crossings use equal-width straight segments near-normal to the boundary where feasible; record exceptions as warnings, not an automatic rejection of an otherwise usable design. UV layers and membranes may cross fields. A device's own sensing structure/local heater may occupy its own membrane; other buses and ordinary leads avoid that membrane. Pads/probe landing areas stay on support, with the currently sourced clearance.

For electrodes, read `references/electrode-resistance.md`: lower ordinary supply-lead resistance while preserving the intended active heater. Inherit port position/direction/width/layer; leave ring electrodes tangentially, match taper wide ends to leads and verify full-width corner coverage. Keep shared centerline stations on inner/outer boundaries when fragmenting curves.

Generate only necessary mask labels on SiN 1/y and metal 10/0, from current parameters/resistance results. Use small, sparse optical text, short titles ≤3 characters, compact dimensions such as `.9um`/`.95um`, and filled glyph polygons away from devices/die boundaries. Respect sourced stroke/clearance rules and keep whole optical strings inside a field where feasible.

Use typed klink RPCs and batch operations where available. Read `references/klayout-klink-workflow.md` before live interaction. Use raw `exec.python` only for a KLayout operation not covered by typed RPCs and only against an explicit test-owned target.

Centerline `PATH` geometry may be retained in a working layout for routing inspection. When the user or clean-export contract requires explicit mask boundaries, expand each completed path to `BOUNDARY/POLYGON` geometry without changing its centerline or width, then verify after GDS read-back that no `PATH` elements remain on the delivery layers.

### 7. Verify

Read `references/verification-and-export.md`. At minimum verify:

- specification and units;
- cell hierarchy and allowed layers;
- component critical dimensions;
- port continuity and route endpoint coincidence;
- route width, bend radius, clearance, and unintended overlap;
- requested tessellation or geometric tolerance;
- DRC when a rule deck or declared constraints exist;
- read-back of the saved GDS.

Use `scripts/process_rules.py` on the saved geometry and semantic ownership manifest for layer mapping, individual solid writefields, full-width containment, pad-group invariants and annotation checks. Use `scripts/geometry_checks.py` for integer range, shared-station fragments, port/corridor checks and protected-layer XOR. Distinguish `error`, soft preference `warning`, and unverified process items. Null process values are not approved zero clearances.

A rendered image is a visual deliverable, not sufficient geometry evidence. Store machine-readable verification results beside the run.

### 8. Export and handoff

Maintain one unambiguous current delivery entry. Generate a separate working layout only when it has an actual editing/debug purpose. Use a fail-closed clean export with explicit top cells and layer allowlist, then re-read it. Authorized in-place updates use candidate → read-back checks → replacement, leaving the current delivery intact on failure. Before cleaning historical versions, check whether current drivers still reference them. Deliver the resolved specification, reproducible driver, clean GDS, verification report and concise run note.

## Failure modes

- If the sketch is topologically ambiguous, generate a labeled interpretation preview or state the chosen reversible default; do not silently invent an additional cavity or connection.
- If a legacy GDS has no semantic ports, treat recovered endpoints as hypotheses until confirmed or matched to source code.
- If KLayout and the klink plugin/client versions disagree, stop live mutation and synchronize them before continuing.
- If a requested tolerance is finer than the layout DBU, reduce the DBU when coordinate range permits or report that the tolerance is not representable.
- If DRC/process data is absent, report geometric checks as geometric checks; do not call the layout fabrication-ready.
- If a PDF text extraction lacks a claimed rule, inspect its figures and adjoining pages before declaring the rule absent. A graphical caption may contain the numeric limit.
- Geometry verification does not validate EBPG GPF/CJOB placement. Preserve coordinate evidence and do not attribute exposure-job failures to source geometry without testing.

## Resources

- `references/design-spec-schema.md` — read when creating or editing a design form.
- `references/component-port-contract.md` — read when adding or migrating reusable components.
- `references/klayout-klink-workflow.md` — read before live KLayout interaction.
- `references/verification-and-export.md` — read before claiming completion or exporting.
- `references/legacy-gds-library-map.md` — read when locating or migrating legacy components.
- `references/sin-process-profile.md` — default user SiN layers, fields, pads, ports and labels; read for this user's SiN work.
- `references/electrode-resistance.md` — read for electrode design or resistance/heating labels.
- `scripts/generate_layout.py` — limited reference microring/Euler generator, polygon delivery by default; not a universal array/membrane router or full SiN DRC.
- `scripts/validate_design_spec.py` — reference-generator specification and representable ring tolerance; `load_spec()` resolves the declared user profile. Other device families use their project driver and the reusable helpers.
- `scripts/process_rules.py` — process default resolver and semantic geometry checks described above.
- `scripts/geometry_checks.py` — shared-station geometry, coordinate range, connectivity corridors and XOR helpers.
- `scripts/electrode_resistance.py` — sourced sheet-resistance formulas and network/heater power accounting.
- `scripts/compare_gds.py` — structural inventory; add `--top-cell` and repeated `--layer` for selected-layer mask geometry XOR.
- `tests/` — contains synthetic fixtures and representative offline/live checks; never place real research assets here.
