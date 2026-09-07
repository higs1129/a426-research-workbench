# Legacy GDS library map

Read this reference during legacy migration. The real legacy library stays external and read-only. Resolve it from an explicit input path or `LEGACY_GDS_ROOT`; never embed a machine-specific absolute path in reusable code.

## Known capability families to index

| Capability | Search terms | Migration evidence |
| --- | --- | --- |
| Basic shapes | `PlaceRect`, `PlaceCirc`, `PlaceTaper` | units, origin/orientation, layer/datatype |
| Waveguides | `Waveguide`, `PlaceSBend`, `PlaceEuler`, `PlaceEulerAngle` | path width, bend convention, endpoint transform |
| Ring cavities | `Microring`, `PlaceMicroring`, `PlaceRingCavity` | radius convention, ring/bus widths, gap, coupling topology |
| Couplers | `pulley`, `coupling`, `taper`, `invtaper` | port coordinates, angular span, transition lengths |
| Chip assembly | `die`, `facet`, `writefield`, `mark` | chip origin, edge pitch, layer map, hierarchy |
| Electrodes | `electrode`, `pad`, `via` | connectivity, metal layers, clearances |

## Indexing procedure

1. Search filenames before content.
2. Prefer the latest demonstrated production entry point, then trace its direct helpers.
3. Record parameter names, units, orientation updates, layer/datatype, and output cell conventions.
4. Select one small representative GDS or parameter set for comparison; do not import a large corpus into tests.
5. Store only generalized findings and external source identifiers in the project component notes. Do not copy real research GDS into the global Skill.

## Current migration note

Legacy Euler helpers may approximate an Euler-like bend by a sequence of arcs whose radii vary from large to small and back. Preserve that historical behavior when byte/shape compatibility is required; prefer a mathematically defined clothoid/Euler bend for new designs and record the deliberate change.
