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

The bundled route is the historical 12 × 90° R40, 500 µm row-spacing, cavity-free numerical benchmark. It is not the latest accepted 750 µm row-spacing chip. Use explicit segments for another route; retain sign ±1 and physical straight lengths. Linear radius variation is not an Euler bend and is not an implemented route primitive.
