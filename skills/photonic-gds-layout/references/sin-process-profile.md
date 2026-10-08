# User SiN process profile

Use `assets/sin-user-process.json` automatically for this user's SiN layout work unless the active specification declares an override. Its values are user-approved conventions, not a universal PDK. `scripts/process_rules.py` provides reusable helpers; pass the resolved defaults and overrides into the generator and retain them in the run specification. Do not infer a different process from a recent chip.

## Exposure groups and layer assignment

| Purpose | 500 µm field | 1000 µm field |
| --- | --- | --- |
| SiN geometry and required optical mask text | 1/0 | 1/1 |
| Writefield rectangles | 30/0 | 30/1 |
| Electrodes and electrical mask text | 10/0 | 10/0 |
| Die | 20/0 | 20/0 |
| Oxide electrode opening | 8/0 | 8/0 |
| Through-oxide etch forming oxide waveguide | 15/0 | 15/0 |
| Silicon opening / deep silicon etch | 50/0 | 50/0 |

`layers_for_writefield(size_um)` is the executable mapping. Only SiN, optical text and writefield datatype follow the exposure group. Mixed field sizes require separate group ownership; do not remap all layers together or split a device polygon merely at a field boundary. Other field sizes require a declared profile mapping.

Each saved field is its own filled rectangular BOX/POLYGON. `writefield_boxes()` removes exact duplicates without unioning adjacent fields. After reading the saved GDS, call `validate_writefields()` separately for each 30/y layer and its expected individual boxes. It detects frames, PATH/TEXT, duplicate instances, merged fields, shifted fields and missing/extra fields. The expected placement list is authoritative input; a rectangle alone does not prove correct exposure-job placement.

## Routing around field boundaries

Plan the full device and all routes together and try alternative routes. Prefer a complete SiN cavity and each bend within one field; check the expanded full-width polygons. Prefer couplers, tapers and entire optical annotation strings away from seams. When crossing is necessary, choose an equal-width straight section close to perpendicular to the boundary; avoid routing along a seam.

`check_field_containment(region, role, layer, fields, override_reason)` checks full-width polygons against individual fields in the feature's exposure group. A failure is a **warning**, including for a cavity or bend. An accepted necessity is recorded as the override reason and remains visible; no automatic rejection of all otherwise feasible layouts is implied. Coupler/taper seam placement needs the same review. UV layers, including membranes, may cross fields and are exempt from the EBL stitching preference.

The containment helper does not solve global routing or determine a near-perpendicular angle tolerance. The profile leaves that numeric tolerance unset. Review crossing directions and local widths against the declared design; report unverified items. No guessed process angle or clearance becomes an automatic failure threshold.

## Pads and optical interfaces

Select `device_kind: single` or `array` and an accepted component profile. Keep pad sizes and intragroup probe-compatible distances fixed; resolve their actual values from that component and record its source. Store group-local geometry separately from each group's translation/rotation anchor. Moving a group preserves local pad relationships. Single-cavity electrode groups commonly have different heights; separate groups have **no common-height default**. Distinct historical profiles may coexist.

`validate_pad_groups()` compares group-local geometry to a sourced accepted component and checks device kind and separate position anchors; it deliberately imposes no equality between group heights. Rotation and actual saved polygon placement still require the component/port and read-back checks. Unresolved pad dimensions, support clearances and process values stay explicit, rather than inheriting an arbitrary recent chip's number.

The profile includes two **named array-component candidates**, not an automatic universal selection: `array-ring-heater-stagger150` has 100×100 µm pads with relative centers (0,0)/(100,150) µm, sourced from Chip7 layout-05; `array-membrane-phase-stagger200` uses the same pad sizes with (0,0)/(100,200) µm, sourced from Chip9's accepted membrane-phase component. The differing offsets are deliberate. Select only when the active accepted component matches; absolute group anchors are not copied. Single-cavity work resolves its own accepted component instead of applying either array candidate by recency. `accepted_local_profiles` can be passed to `validate_pad_groups()` after selecting the correct component.

Current overridable optical interface defaults are a 0.4 µm narrow end, 200 µm total narrow section (100 µm inside and 100 µm outside), and 300 µm linear taper. Apply 127 µm center spacing only when a fiber-array interface is requested. When any segment changes, recompute adjacent endpoints and check first-bend/taper overlap and port continuity. These are user process defaults, not universal mandatory geometry.

## Required mask annotation

Add only needed labels on the device's SiN 1/y or electrical 10/0 layer. Place them away from actual structures and die boundaries; avoid touching. Optical text should be small and sparse but respect the sourced minimum stroke. Prefer the entire optical string inside one field. Text must be filled glyph polygons in delivery GDS, not TEXT or stroked PATH elements.

Use titles of at most 3 characters, for example `R` or `Dfi`. `dimension_label()` and `format_nm_as_um()` generate compact values from current numeric data: 900 nm → `.9um`, 950 nm → `.95um`. Conversion removes redundant zeros without rounding away scan differences. Generate dimensions and resistance labels from the same current parameter/electrical records that drive geometry; do not copy stale labels.

`validate_annotation_geometry()` verifies explicit annotation ownership, polygon status and collisions with supplied keepouts. Prefer `validate_annotation_cell()` on an annotation-only cell after read-back: it inspects every populated layer and actual TEXT/PATH elements rather than accepting a generator's polygon flag. Supply actual structure geometry and declared die-boundary keepout strips; these helpers do not automatically identify text in an arbitrary unlabeled GDS. At zero declared clearance, one DBU expansion is used solely to detect edge touching. A sourced minimum text stroke, die clearance and structure clearance are still required for process DRC; null profile values do not mean zero is fabrication-approved.

## API use and verification scope

All geometry checks accept integer DBU KLayout geometry. Creation helper inputs are micrometres and an explicit DBU. Use actual geometry from the delivery GDS read-back and a semantic manifest identifying feature and annotation ownership, rather than trusting generator flags alone. `validate_layer_assignment()` checks semantic role → layer/datatype. `Finding` includes severity, code, message and `to_dict()` for the run report.

Run the synthetic regressions from the repository root:

```powershell
python -B -m unittest discover -s skills/photonic-gds-layout/tests -p test_process_rules.py -v
```

Tests demonstrate wrong datatype, hollow/merged/duplicate fields, centerline-only containment mistakes, text collisions, and changed pad spacing being detected. Synthetic test pad values are not process defaults. This helper set is focused geometry verification, not a complete DRC or validation of an EBPG GPF/CJOB exposure job.

`resolve_process_defaults(spec)` reads the selected `process.profile`, resolves all `exposure_groups`, fills null single-group layer mappings and supplies the optical-interface and SiN curve defaults. It rejects incompatible explicit layers and inconsistent narrow-section lengths rather than silently changing geometry. The maintained intake template selects this user profile. Non-SiN or a deliberately different process should select its own explicit profile.

SiN curve acceptance is **three-point perpendicular distance <0.1 nm**, from the guide's page-7 image (“around 0.1 nm”) plus the user's stricter clarification. The executable profile records this separately from other-layer ~1 µm point spacing. `design-spec-schema.md` defines the metric, uniform sampling and rounding margin; an arc sagitta is not this metric.
