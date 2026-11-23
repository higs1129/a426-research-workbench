# SiN photonics source moved

The single maintained source is now the self-contained [sin-photonics Skill](../../skills/sin-photonics/README.md).

Its `scripts/toolkit/` contains the Python solver, COMSOL model definitions and300 nm material parameters; `examples/` contains runnable configurations. There is no separate toolkit to install or configure.

From the Workbench root:

```powershell
python -m pip install -r skills/sin-photonics/requirements.txt
python skills/sin-photonics/scripts/run.py doctor
python skills/sin-photonics/scripts/run.py ring-bus --config skills/sin-photonics/examples/ring-scan-small.json --plan
```

This directory is a migration pointer, not a second source tree. The former reference-package builders are retired; use the Skill's Git distribution.
