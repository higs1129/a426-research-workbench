---
name: photonic-gds-layout
description: Creates, modifies, migrates, and verifies photonic or microdevice GDS layouts through KLayout/klink from user sketches, KLayout selections, structured parameters, component ports, routing constraints, and clean-export requirements. Use for resonators, cavities, waveguides, couplers, Euler routes, arrays, chip facets, and legacy GDS migration. Do not use for fabrication records, simulation-only analysis, or decorative scientific illustrations.
metadata:
  version: "1.1"
  skill-author: "Personal Research Workflow"
---

# Photonic GDS Layout

## Purpose and boundaries

Turn a conceptual sketch, a live KLayout selection, or a legacy layout into a reproducible photonic GDS design with explicit parameters, reusable components, connected ports, verification evidence, and a clean export.

The Skill orchestrates design decisions and KLayout/klink operations. Process-specific geometry, PDK data, and reusable device code belong to the active layout project, not inside this Skill. Treat legacy libraries and research records as read-only unless the current project explicitly owns them.

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

### 3. Acquire design intent

- For conceptual topology, ask the user to draw in the daily research canvas and notify the agent when ready. Read the current-day Markdown/state/preview as read-only evidence.
- For exact geometry, ask the user to draw/select in KLayout and click `SEND`. Resolve the durable selection or ruler geometry through klink; do not infer precise coordinates from a screenshot.
- When both exist, the daily sketch defines topology and the KLayout selection defines coordinates and objects.

### 4. Build and validate the specification

Copy `assets/design-spec.template.yaml` into the current run directory, prefill known values, and mark unresolved fields. Read `references/design-spec-schema.md` for field semantics. Run:

```powershell
python scripts/validate_design_spec.py path\to\design-spec.yaml
```

Freeze the specification once the topology, layers, unit conventions, and export target are coherent. This is the first confirmation gate.

### 5. Resolve components

For each unit, search in this order:

1. the active project component/toolbox library;
2. the indexed legacy implementation, read-only;
3. a new parameterized implementation.

Every reusable component must satisfy `references/component-port-contract.md`. Generate one unit first and inspect its critical dimensions, origin, ports, layer set, and bounding box before arraying or routing. User acceptance of this unit is the second confirmation gate.

### 6. Assemble and route

Place units hierarchically. Connect named ports rather than guessed polygon endpoints. Keep the cavity coupling segment straight when specified; use Euler bends for edge transitions when requested. Preserve explicit minimum radius, width, clearance, and keepout constraints.

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

A rendered image is a visual deliverable, not sufficient geometry evidence. Store machine-readable verification results beside the run.

### 8. Export and handoff

Keep a working layout with markers separate from the delivery GDS. Use a fail-closed clean export with explicit top cells and layer allowlist, then re-read the exported file. Deliver the specification, reproducible driver, working/clean GDS as applicable, verification report, and a concise run note.

## Failure modes

- If the sketch is topologically ambiguous, generate a labeled interpretation preview or state the chosen reversible default; do not silently invent an additional cavity or connection.
- If a legacy GDS has no semantic ports, treat recovered endpoints as hypotheses until confirmed or matched to source code.
- If KLayout and the klink plugin/client versions disagree, stop live mutation and synchronize them before continuing.
- If a requested tolerance is finer than the layout DBU, reduce the DBU when coordinate range permits or report that the tolerance is not representable.
- If DRC/process data is absent, report geometric checks as geometric checks; do not call the layout fabrication-ready.

## Resources

- `references/design-spec-schema.md` — read when creating or editing a design form.
- `references/component-port-contract.md` — read when adding or migrating reusable components.
- `references/klayout-klink-workflow.md` — read before live KLayout interaction.
- `references/verification-and-export.md` — read before claiming completion or exporting.
- `references/legacy-gds-library-map.md` — read when locating or migrating legacy components.
- `scripts/generate_layout.py` — deterministic reference generator for the included microring/Euler-route case.
- `scripts/validate_design_spec.py` — validates form structure, units, topology references, and representable tolerance.
- `scripts/compare_gds.py` — compares hierarchy, layers, bounding boxes, and stored shape counts.
- `tests/` — contains synthetic fixtures and representative offline/live checks; never place real research assets here.
