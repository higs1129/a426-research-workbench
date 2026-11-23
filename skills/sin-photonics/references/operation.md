# Program operation

The portable package has `toolkit/`, `modes/`, `models/`, `evidence/`, `plotting-runtime/`, and a checksum manifest. COMSOL is needed for changed geometry, not for replaying the frozen field reference. Python needs NumPy, SciPy and jsonschema. The native solver was exercised with COMSOL 6.1; a COMSOL license and Wave Optics functionality are required.

From a portable package root:

```powershell
$env:PYTHONPATH = (Resolve-Path toolkit).Path
python -m sinphotonics ring-bus --config toolkit/examples/ring-reference.json --library modes --output my-ring-result
python -m sinphotonics bends --config toolkit/examples/route-r40-reference.json --library modes --output my-route-result
```

For new geometry, omit `--library` and supply the installed COMSOL `bin/win64` directory through `--comsol-bin` or `COMSOL_BIN`. Start with `toolkit/examples/ring-modified.json`; paths are resolved from explicit arguments, not from a historical experiment directory. The output directory must not already exist. See the toolkit README for package installation, material bounds, native inspection and reference-package reconstruction.

The installed Skill launcher is optional:

```text
python scripts/run.py --toolkit <toolkit-directory> ring-bus --config <config.json> --output <new-output> --comsol-bin <bin-directory>
```

The launcher contains no algorithm. It prepends the explicitly chosen toolkit to PYTHONPATH and invokes that package with the current Python interpreter.

`config.schema.json` rejects unknown fields. SI units are used internally; configuration names declare nm/µm/degrees. Both widths and edge gaps share `size_reference`. For a trapezoid with height h and wall θ, bottom width = mid width + h cotθ; bottom gap = mid gap − h cotθ. Top conversions use twice that correction. Radius always means ring centerline.

The default eigenvalue search positions follow the frozen width-dependent TE scan. If field inspection identifies a shifted branch, `mode_search` may specify numeric `shifts` by TE0/TE1/TM0 and an `eigenmodes` count. These are solver search hints, not material dispersion inputs. Ring-bus scans isolate missing branches per geometry; partial-basis values are diagnostic and missing values remain null. Bends/routes require their requested basis and fail on a missing mode. `bend-two-mode.json` is the native TE0/TE1 conversion example.

For multiple ring/bus widths, radii or target wavelengths use `ring-scan-small.json`. Scan arrays override the corresponding scalar axes and form a Cartesian product. Run `ring-bus --config <config> --plan` first; it writes nothing. The default limits are 32 native channel/parameter cases and 128 coupling cases. Explicit `--max-native-cases` / `--max-coupling-cases` change those budgets. The planner merges overlapping λ±2 nm anchors and excludes gap from FEM work. Each case and dispersion stencil references `native-mode-map.json`; native families also include `native-map.csv` and selection manifests. A native output can be reused as a library when it has a verified `library.json` indexing its `ring/raw` and `bus/raw` layouts and mapping manifests.

Leave `integration.extent_um` omitted for automatic longitudinal-window planning. It starts at 30 µm when that leaves enough expansions; otherwise at Lmax/growth^consecutive_passes, with Lmax below 0.8R and the configured maximum. An explicit initial value must permit the required number of expansions. `integration.window` controls tolerances/limits; full comparison history is in `result.json`. Reaching a limit without consecutive passes remains diagnostic. To improve a sampling-support failure, export a wider physical field domain; merely enlarging a zero-filled integral cannot recover missing fields.

The portable package links the standalone Chinese `model-and-equations.html`. Rebuild from maintained source with `python toolkit/scripts/build_guide.py --output <allowed-output>/model-and-equations.html`. It explains structures, field/eigenvalue signs, ng/FSR/Q, complex coupling, diagonal phase, Gram projection and coherent routes, with embedded semantic SVG and function mappings. Generation validates XML/roles/links without browser aesthetic checks or duplicate graphics.

The bundled route is the historical 12 × 90° R40, 500 µm row-spacing, cavity-free numerical benchmark. It is not the latest accepted 750 µm row-spacing chip. Use explicit segments for another route; retain sign ±1 and physical straight lengths. Linear radius variation is not an Euler bend and is not an implemented route primitive.
