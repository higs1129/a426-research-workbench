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

Parameter values belong to the run specification or project PDK. Do not hide process constants inside the Skill.

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

## Migration acceptance

A migrated component is accepted only after matching the legacy reference on the parameters that matter for reuse: layer set, critical dimensions, bounding box, port locations/directions, and representative geometry counts or sampled coordinates. Record deliberate differences rather than forcing byte equality when the legacy file lacks semantic structure.
