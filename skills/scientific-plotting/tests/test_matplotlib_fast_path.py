"""Representative timed regression test for the Matplotlib editable fast path."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from time import perf_counter


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
RENDERER = SKILL_ROOT / "scripts" / "render_matplotlib_editable.py"
PLOT_SCRIPT = FIXTURES / "matplotlib_standard_plot.py"
OUTPUT = FIXTURES / "matplotlib-fast-path.html"
TIMING = FIXTURES / "matplotlib-fast-path-timing.json"


def elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def main() -> None:
    test_start = perf_counter()
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"

    try:
        process = subprocess.run(
            [
                sys.executable,
                str(RENDERER),
                "--plot-script",
                str(PLOT_SCRIPT),
                "--profile-id",
                "90mm-single",
                "--output",
                str(OUTPUT),
                "--timing-output",
                str(TIMING),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
    except subprocess.CalledProcessError as error:
        raise AssertionError(
            "Fast-path renderer failed.\n"
            f"stdout:\n{error.stdout}\n"
            f"stderr:\n{error.stderr}"
        ) from error

    validation_start = perf_counter()
    html = OUTPUT.read_text(encoding="utf-8")
    required = {
        "inline SVG": "<svg",
        "editable SVG text": "<text",
        "shared runtime": 'data-sf-runtime-version="1.0.0"',
        "fast-path identity": '"renderer":"matplotlib-svg-fast-path"',
        "runtime-ready hook": 'dataset.sfReady = "true"',
        "box zoom": 'data-sf-action="box-zoom"',
        "pan": 'data-sf-action="pan"',
        "hover layer": 'id="inspection-overlay"',
        "editor": 'data-sf-field="lineWidthPt"',
        "layout mode": 'data-sf-action="edit-layout"',
        "layout undo": 'data-sf-action="undo-layout"',
        "layout numeric offset": 'data-sf-layout-field="x"',
        "layout role bridge": "data-sf-layout-role",
        "collective x tick-label role": 'xTicks: {id: "sf-x-tick-labels"',
        "collective y tick-label role": 'yTicks: {id: "sf-y-tick-labels"',
        "whole-element layout hit target": "data-sf-layout-hit",
        "legend role": 'id="sf-legend"',
        "tick-label gap token": '"tickLabelGapEm":0.28',
        "legend-axis gap token": '"legendAxisGapEm":0.25',
        "title-legend gap token": '"titleLegendGapEm":0.25',
        "top-layout safety token": '"topLayoutSafetyEm":0.4',
        "fixed-step tick bridge": "fixedStepTicks",
        "browser title-legend check": "scheduleAutomaticTopLayout",
    }
    missing = [label for label, marker in required.items() if marker not in html]
    if missing:
        raise AssertionError(f"Missing fast-path invariants: {', '.join(missing)}")
    if "90 mm single-column" in html and "185 mm double-column width" in html:
        raise AssertionError("Formal HTML embedded more than one delivery profile.")

    def embedded_json(element_id: str) -> dict:
        match = re.search(
            rf'<script id="{re.escape(element_id)}"[^>]*>(.*?)</script>',
            html,
            flags=re.DOTALL,
        )
        if not match:
            raise AssertionError(f"Missing embedded JSON payload: {element_id}")
        return json.loads(match.group(1))

    embedded_profile = embedded_json("scientific-figure-profile")
    embedded_data = embedded_json("scientific-figure-data")
    if embedded_profile["tickLabelGapEm"] != 0.28:
        raise AssertionError("Unexpected default tick-label gap.")
    if embedded_profile["legendAxisGapEm"] != 0.25:
        raise AssertionError("Unexpected default legend-axis gap.")
    if embedded_profile["titleLegendGapEm"] != 0.25:
        raise AssertionError("Unexpected default title-legend gap.")
    if embedded_profile["topLayoutSafetyEm"] != 0.4:
        raise AssertionError("Unexpected browser-metric top-layout safety reserve.")
    if embedded_data["layoutDefaults"]["legend"]["y"] <= 0:
        raise AssertionError("Top legend was not compacted toward the axes.")
    if embedded_data["ticks"]["y"]["mode"] != "fixed-step":
        raise AssertionError("Explicit MultipleLocator was not preserved in the HTML payload.")
    if abs(embedded_data["ticks"]["y"]["step"] - 0.2) > 1e-9:
        raise AssertionError("Explicit 0.2 y-axis interval was not preserved.")
    if embedded_data["ticks"]["x"]["mode"] != "nice":
        raise AssertionError("The default x-axis should retain shared nice ticks.")
    if embedded_data["layoutDiagnostics"]["titleLegend"]["status"] != "adjusted":
        raise AssertionError("The title/legend collision was not detected and resolved.")
    if embedded_data["layoutDefaults"]["title"]["y"] >= 0:
        raise AssertionError("The title was not moved above the compact top legend.")
    if embedded_data["layoutDiagnostics"]["titleLegend"]["topReservePt"] < 3.5:
        raise AssertionError("The title/legend stack lacks the browser-metric safety reserve.")

    report = json.loads(TIMING.read_text(encoding="utf-8"))
    report["timings"]["deterministic_validation_ms"] = elapsed_ms(validation_start)
    report["timings"]["test_process_total_ms"] = elapsed_ms(test_start)
    report["checks"] = sorted(required)
    TIMING.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
