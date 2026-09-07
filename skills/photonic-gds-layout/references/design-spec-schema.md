# Design specification schema

Read this reference when creating or updating a run-level `design-spec.yaml`.

## Required groups

### `design`

- `name`: stable run/device identifier.
- `top_cell`: valid GDS top-cell name.
- `mode`: `new`, `live-edit`, or `legacy-migration`.
- `dbu_um`: database unit in micrometres. It must be fine enough to represent the strictest coordinate tolerance while retaining sufficient coordinate range.
- `source_intent`: short description of the sketch, KLayout selection id, or source layout.

### `layers`

Each logical layer maps to `[layer, datatype]`. Reserve annotation/working-marker layers separately from delivery layers. `export.allowlist` must explicitly name logical layers.

### `unit_cell`

- `family`: component family such as `microring`, `disk`, `racetrack`, `spiral`, or `custom`.
- `source`: `project-library`, `legacy`, `klayout-selection`, or `new`.
- `parameters`: component-specific numbers with unit-bearing names such as `radius_um` and `width_um`.
- `tessellation`: optional geometry approximation contract. For a circular centerline, `midpoint_chord_deviation_nm` means the perpendicular distance from the middle point to the chord joining the two adjacent-neighbour points.

### `waveguide`

- `width_um`, `coupling_gap_um`, and `coupling_length_um` define the straight cavity-coupling section.
- `route_kind`: use `euler-edge-transition` when the central straight bus connects to displaced edge straights through Euler bends.
- `euler`: contains the minimum radius and sampling density for each bend.
- `left_edge` and `right_edge`: contain the edge-straight lengths and vertical offsets from the coupling bus.

### `ports`

Every port has a unique `name`, a `role`, and an orientation convention. Generated coordinates may be omitted from the input form and written into the verification report.

### `verification`

Declare requested numeric tolerances and checks. A check that lacks process data must not be silently promoted into a process DRC.

### `export`

- `working_gds`: optional layout retaining helper layers.
- `clean_gds`: delivery layout.
- `allowlist`: logical layers allowed into the clean file.

## Units

Use micrometres for geometry and degrees for angles. Encode units in field names. Convert to nanometres only in reports where it makes the requested tolerance easier to read.

## Circular tessellation

For centerline radius `R` and `N` equal angular segments, the midpoint-to-two-neighbour chord deviation is:

```text
s = R * (1 - cos(2*pi/N))
```

Choose the nearest integer `N` to the analytic target, report the achieved value, and verify it after GDS read-back. Ensure `dbu_um` is materially smaller than the requested deviation.
