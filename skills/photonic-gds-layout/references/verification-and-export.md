# Verification and export

Read this reference before claiming a layout is complete or producing a delivery GDS.

## Specification checks

- All geometry-bearing fields have explicit units.
- The DBU represents the strictest requested coordinate tolerance.
- Port and connection references resolve uniquely.
- Layer mappings and clean-export allowlist are explicit.
- Assumed defaults remain visible in the run specification.

## Geometry checks

- Re-read the written GDS with KLayout's database API.
- Confirm top-cell names, DBU, hierarchy, layers, and bounding boxes.
- Confirm critical component dimensions from stored geometry.
- Confirm route endpoints and port centers coincide within declared tolerance.
- Check continuity, zero-length segments, self-intersection, unintended overlap, width, minimum radius, and keepout clearance.
- For tessellated curves, compute the requested approximation metric on read-back coordinates rather than trusting generator inputs alone.

## Process checks

Run KLayout DRC/LVS when the project supplies a valid deck or explicit process/connectivity profile. Keep geometric verification and process verification separately labeled. Absence of violations in an unspecified or wrong deck is not evidence.

## Clean export

1. Save the full working layout.
2. Export only explicit top cells and allowed design layers.
3. Remove helper PCells/markers by semantic type where possible.
4. Re-read the exported GDS into a fresh layout.
5. Refuse delivery if unexpected top cells/layers remain or expected design content is missing.

## Minimum run evidence

- resolved `design-spec.yaml`;
- reproducible driver or component source;
- working and/or clean GDS;
- machine-readable verification report;
- visual preview when requested;
- concise note listing assumptions, passed checks, remaining process checks, and source references.
