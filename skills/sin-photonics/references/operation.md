# Program operation

Run this Skill's `scripts/run.py`; every path below is relative to the Skill directory. The entry point loads only the bundled toolkit and renderer. It needs neither a separately installed toolkit nor another Skill. Install the declared Python dependencies with the same interpreter, using `python -m pip install -r requirements.txt`.

```powershell
python scripts/run.py doctor
python scripts/run.py ring-bus --config examples/ring-scan-small.json --plan
python scripts/run.py ring-bus --config examples/ring-reference.json --output <new-output> --comsol-bin <COMSOL-bin-win64>
python scripts/run.py bends --config examples/bend-single.json --output <new-output> --comsol-bin <COMSOL-bin-win64>
python scripts/run.py guide --output <allowed-output>/model-and-equations.html
```

`doctor --require-comsol --comsol-bin <bin>` checks executable discovery as well as Python and bundled-resource availability. A COMSOL license and electromagnetic mode functionality are required for actual FEM solves. The launcher currently supports Windows COMSOL6.1; other platforms are unverified. `--plan`, the model guide, and explicit field-library replays do not need COMSOL. Command paths are explicit and output directories must be new. `routes` is an alias of `bends`.

An existing matching field library is optional. Supply `--library <library>` only when its verified `library.json`, material, cross section, widths, radii, wavelengths and requested branches match. Legacy libraries use `ring/`, `bus/`, `straight/`, `bend/` NPZ folders. Native libraries may use `ring/raw` and `bus/raw` plus selection manifests and maps. Stored widths are always bottom-defined. The Skill contains the complete model definitions and material coefficients, not the optional raw field archive.

`scripts/toolkit/sinphotonics/config.schema.json` rejects unknown fields. Units are declared in configuration names; SI is used internally. `cross_section.size_reference` applies to both widths and gap. For height h and wall θ, bottom width=mid width+h cotθ; bottom gap=mid gap−h cotθ. Top corrections are twice these. Radius is the ring centerline radius. All material dispersion comes from the bundled300 nm process reference.

For scans use arrays `ring_widths_um`, `bus_widths_um`, `ring_radii_um`, `wavelengths_nm` under `scan`. They override their scalar axes and form a Cartesian product. First inspect `--plan`: it writes nothing and merges overlapping λ±2 nm derivative anchors; gap never triggers FEM. Default limits are32 native channel/parameter cases and128 coupling cases. Explicit `--max-native-cases` / `--max-coupling-cases` raise these budgets. Each family uses one native MPH sweep. `native-mode-map.json`, `native-map.csv` and manifests link each case and derivative stencil to model/study/dataset/outer/eigenmode identities.

Mode search follows width-dependent TE seeds. `mode_search` can explicitly set numeric `shifts` and `eigenmodes`; these are search hints, not predicted indices. A missing TE1 in a ring-bus scan is recorded per geometry; partial-basis results stay diagnostic with null missing-channel values. Other geometries continue. Bends/routes require their requested basis and fail on a missing mode. See `examples/bend-two-mode.json` for explicit TE0/TE1 conversion.

Omit `integration.extent_um` for automatic longitudinal planning. It starts at30 µm when that leaves enough expansions, otherwise at Lmax/growth^consecutive_passes, where Lmax is below0.8R and the configured maximum. Explicit initial values must leave enough expansions. `integration.window` controls tolerances/limits; results retain every comparison. A limit reached without consecutive passes remains diagnostic. A failed sampling-support check requires a wider exported field domain; extending a zero-filled integral cannot recover missing fields.

The generated Chinese model guide is standalone HTML with4 semantic SVG diagrams, material coefficients, formulas and function mappings. Generation checks native SVG markup, XML, roles, links and label anchors; it does not perform browser aesthetic review or export duplicate graphic files. Reports contain configuration, scalar tables, complex NPZ and explicit limitations.

The historical R40 route example represents12×90° arcs,500 µm row spacing and no cavities. It is not the later750 µm-row-spacing chip. Use explicit segments for another route; preserve turn sign ±1 and physical straight lengths. Euler/arbitrary-curvature bends are not implemented.

## Maintenance

Algorithm source lives only in `scripts/toolkit/`. Tests requiring real data accept explicit input paths; they are optional and separate from installation. The old archive builders are retired. Standalone distribution, Git installation and dependency snapshot maintenance are described in [../README.md](../README.md).
