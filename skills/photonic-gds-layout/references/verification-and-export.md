# Verification and export

Read this reference before claiming a layout is complete or producing a delivery GDS.

## Specification checks

- All geometry-bearing fields have explicit units.
- The DBU represents the strictest requested coordinate tolerance.
- Port and connection references resolve uniquely.
- Layer mappings and clean-export allowlist are explicit.
- Assumed defaults remain visible in the run specification.
- Required process defaults and overrides are resolved once, with source identifiers. Single-cavity and array pad components are distinct; group anchors do not imply shared heights.
- Local changes declare editable/preserved/derived items. A single scan table drives geometry, labels and manifest; pair rotation and common-slot choice are separate fields.

## Geometry checks

- Re-read the written GDS with KLayout's database API.
- Confirm top-cell names, DBU, hierarchy, layers, and bounding boxes.
- Confirm critical component dimensions from stored geometry.
- Confirm route endpoints and port centers coincide within declared tolerance.
- Check continuity, zero-length segments, self-intersection, unintended overlap, width, minimum radius, and keepout clearance.
- For tessellated curves, compute the requested approximation metric on read-back coordinates rather than trusting generator inputs alone.
- SiN uses the maximum middle-vertex to neighbour-line distance **<0.1 nm** with uniform curve stations; reserve DBU rounding margin. Check both boundaries, common stations across fragments, width, curvature and abnormally long chords. UV curve spacing is about 1 µm; straight edges need no artificial densification. See the manual image/source distinction in `design-spec-schema.md`.
- Verify filled individual writefield rectangles from saved geometry, removing only exact duplicates. Do not union adjacent fields. Full-width SiN containment is a preference with reported exceptions; UV is exempt from stitching constraints.
- Check required mask text is polygon geometry on the correct SiN 1/y or metal 10/0 layer, preserves scan differences and avoids structure/die-boundary contact. Where numeric stroke/clearance is unavailable report that scope explicitly.
- Trace ordinary lead and bus keepouts versus owned membranes; verify probe landings are on support. Allowed own sensing structure/local heater is not an overlap violation.
- Check intended port faces and full-width joint corridors independently of metadata; watch tangent electrode exits, taper wide-end mismatch and right-angle necking.
- Compare protected layers by recursive flattened geometry XOR or a coordinate/transform signature, not just bounding boxes or shape counts. Normalize explicit inverse pair transforms before comparing nominally repeated devices. `geometry_checks.compare_geometry()` needs equal DBU and mask polygons/PATH; it does not compare hierarchy or text semantics.
- For an intentional datatype conversion, normalize the explicit source→target layer mapping in a read-only comparison copy before XOR. Preserve the full device geometry; a moved layer must not appear as a false deletion. If new tessellation is required, declare that boundary resampling as an allowed change, quantify geometric error and check the new curve bound; do not claim an exact original-vertex match. `compare_gds.py --top-cell TOP --layer 10/0` compares selected physical geometry and exits nonzero on mismatch; without these flags its report is explicitly inventory-only.

## Process checks

Run KLayout DRC/LVS when the project supplies a valid deck or explicit process/connectivity profile. Keep geometric verification and process verification separately labeled. Absence of violations in an unspecified or wrong deck is not evidence.

## Clean export

1. Retain a working layout only when it serves an editing/debug purpose. Preserve originals and the current authoritative delivery.
2. Preflight input top cells, colliding cell names, PATH/TEXT, long XY records and explicit layer ownership. Namespace imported cells as needed; expand PATH and polygonize text only as the contract requires, verifying the change. Do not rewrite source files.
3. Before integer conversion, check DBU against **absolute coordinates and full span**, overhangs, instance transforms, precision needs and downstream limits. `geometry_checks.check_dbu_extent()` covers signed-coordinate and span bounds; no particular DBU (including 0.04 nm) is universal. Respect the chosen writer/consumer's polygon record limit and fragment with shared stations, not independently sampled boundaries.
4. Export a candidate with explicit tops/layer allowlist and semantic removal of helpers. Remap datatype by whole-device/exposure ownership, including labels/tapers; never clip polygons at field boundaries merely to assign layers. Shared cells owned by different exposure types require separate copies before mapping.
5. Read the saved candidate into a fresh layout. Check source-vs-saved geometry, unchanged layers, transforms and requested geometry invariants; refuse replacement on error. Warnings and unverified process checks remain visible.
6. Replace an existing delivery only within authorized scope after these checks. Keep one current delivery pointer/entry. Check references before deleting old revisions. For split exports preserve common origin/transforms and provide shared extent/coordinate documentation.

GDS geometry acceptance does not establish EBPG GPF/CJOB origin, job placement or exposure correctness. Investigate source geometry and job transforms separately. Preserve evidence and avoid unsupported blame or exposure guarantees. Optical/thermal simulation conclusions need their own mode, mesh and convergence evidence; a valid GDS or successful solver run is not proof of performance.

## Minimum run evidence

- resolved `design-spec.yaml`;
- reproducible driver or component source;
- working and/or clean GDS;
- machine-readable verification report;
- visual preview when requested;
- concise note listing assumptions, passed checks, remaining process checks, and source references.

## Executable checks and limits

- `process_rules.resolve_process_defaults()` fills the declared user profile; geometry generation still belongs to the project driver.
- `validate_writefields()` examines recursive saved shapes, including duplicate instances and hollow frames. `check_field_containment()` uses full polygons and produces warnings, not fabricated hard constraints.
- `validate_annotation_cell()` requires a semantic annotation-only cell; arbitrary unlabeled polygons cannot automatically be identified as text.
- `geometry_checks.check_required_corridors()` needs independently specified required footprints. `check_curve_fragment()` expects paired boundary stations; arbitrary imported polygon ordering needs an appropriate semantic reader first.
- `electrode_resistance.solve_network()` (see its reference for arguments) evaluates the supplied actual network, not electrical connectivity inferred from GDS.
- The single-group reference generator derives enough Euler samples and verifies saved ring and route boundaries against the strict limit, including straight/curve junctions and merged fragment seams; only verified terminal cap corners are excluded. A curve is not exempt merely because its adjacent edges are long. Project arrays, membranes and other custom curves still require their geometry-specific checks. Multi-group specifications need a group-aware project driver; the reference generator refuses them. List unimplemented checks honestly.

Run tests with outputs confined to `tests/.runs/` (create the directory first), e.g. `python -B -m pytest tests --basetemp=tests/.runs/review-run -q` from the Skill root. `pytest` may be provided by the project's environment; optional local dependencies and all generated GDS/reports remain ignored. The tests use synthetic geometry and must not modify real designs.
