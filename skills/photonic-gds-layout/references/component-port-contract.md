# Component and port contract

Read this reference when creating, accepting, or migrating a reusable layout component.

## Component identity

Each component exposes:

- a stable family/name and parameter dictionary;
- a documented local origin and default orientation;
- the layer set and top cell;
- a bounding box and optional keepout polygons;
- named ports;
- critical dimensions and their verification method.

## Shared geometry source

When several mask layers describe one device, the component or resolved design
object is the source of truth for shared cavity centers, radii, ports, membrane
boundaries and other cross-layer anchors. Optical, electrode, opening and
membrane modules consume those definitions and may add layer-specific geometry;
they do not recover normal-development coordinates by reading an earlier GDS.
If an external incoming layout or a source-missing migration must be preserved,
mark the affected layer as external-input or frozen-geometry reuse, record the
missing source and required input hash, and do not imply that a parameterized
source was recovered.

Parameter values belong to the resolved run specification, the explicit user process profile or project PDK. Keep sources visible rather than hiding constants in geometry code.

## Port fields

Each port records:

- `name` unique within the component;
- `kind`: optical, electrical, mechanical, or alignment;
- center coordinate in micrometres;
- orientation in degrees, where 0 points along +x and angles increase counter-clockwise;
- width and logical layer;
- connection role such as input, output, bus-left, bus-right, or electrode.

Two directly connected ports must agree on center and layer, have compatible widths, and face opposite directions unless an explicit transition component sits between them.

## Cavity convention

For a microring, `radius_um` refers to the centerline unless the specification explicitly says inner or outer radius. `width_um` is symmetric about that centerline. Report inner and outer radii in verification evidence.

## Route convention

Routes consume named ports and preserve width unless a taper is explicit. Euler bends declare their minimum curvature radius and sampling/approximation method. A straight coupling bus remains a geometrically straight segment across the declared coupling span.

Every added segment inherits the preceding endpoint position, direction, width and layer. A ring electrode leaves tangentially; a taper's wide end equals its lead width. At a right-angle joint, fill the intended conductor footprint with overlapping solid coverage and check the full-width corridor for gaps/necking, not just centerline contact. `geometry_checks.check_ports()` verifies metadata; `check_required_corridors()` independently tests the intended joint footprint against actual mask polygons. Define corridors from the required width, not from an already narrowed result.

`R` is the ring centerline radius; `gap` is edge-to-edge distance. Specify top/bottom width and gap conventions for sloped sidewalls. Euler R denotes minimum curvature radius, not bend footprint size. Resolve facet taper/narrow section and optional fiber-array pitch from the user's overridable process profile, then recompute and check the first bend when a segment changes.

## Pad and membrane ownership

Keep pad-group local geometry (pad size, relative centers, probe spacing) separate from each group's anchor/rotation and from device placement. Single-cavity and array components are distinct; single-cavity pad groups commonly have different heights. Moving a group preserves local geometry. Check its actual exported geometry and preserve unrelated groups/layers on edits.

Attach membrane ownership and allowed feature roles to each device. Its sensing structure and explicitly allowed local heater may lie on its own membrane. Unrelated buses and ordinary supply leads avoid it. Pads and probe landings remain in support regions with sourced clearance; do not invent a new numeric keepout.

## Migration acceptance

A migrated component is accepted only after matching the legacy reference on the parameters that matter for reuse: layer set, critical dimensions, bounding box, port locations/directions, and representative geometry counts or sampled coordinates. Record deliberate differences rather than forcing byte equality when the legacy file lacks semantic structure.

An accepted component is not selected by newest timestamp or edit count. Record
the explicit accepted/exposed state for each relevant layer and keep candidates
separate until a user-authorized acceptance update.
