"""Embed validated figure components in an offline report; never redraw a figure."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bundle(shell: str, figures: list[dict], base: Path) -> str:
    seen = set()
    for item in figures:
        key = item["id"]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key) or key in seen:
            raise ValueError("Each figure needs a unique simple id")
        seen.add(key)
        document = (base / item["html"]).read_text(encoding="utf-8")
        if '"componentVersion":"1.0"' not in document or "window.ScientificFigure =" not in document:
            raise ValueError(f"{key}: missing maintained component API; regenerate through the supported renderer, or confirm an adapter extension")
        marker = f"<!-- SCIENTIFIC_FIGURE:{key} -->"
        if shell.count(marker) != 1:
            raise ValueError(f"Expected one {marker}")
        label = html.escape(item.get("label", key), quote=True)
        element = (f'<section class="sf-report-figure" data-sf-figure="{key}">'
                   f'<button type="button" data-sf-expand aria-expanded="false">放大 / 收起图形</button>'
                   f'<iframe title="{label}" srcdoc="{html.escape(document, quote=True)}"></iframe></section>')
        shell = shell.replace(marker, element)
    marker = "<!-- SCIENTIFIC_REPORT_RUNTIME -->"
    if shell.count(marker) != 1 or "<!-- SCIENTIFIC_FIGURE:" in shell:
        raise ValueError("Report needs one runtime marker and exactly one declared component per figure slot")
    runtime = (ROOT / "assets/report-figure-host.js").read_text(encoding="utf-8")
    css = """.sf-report-figure{background:white;border:1px solid #ccd1d5;padding:8px}
.sf-report-figure>iframe{display:block;width:100%;height:560px;border:0}
.sf-report-figure.sf-expanded{position:fixed;inset:2vh 2vw;z-index:10000;overflow:auto;box-shadow:0 0 0 100vmax #0008}
.sf-report-figure.sf-expanded>iframe{height:calc(94vh - 50px)}"""
    return shell.replace(marker, f"<style>{css}</style><script>{runtime}</script>")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", type=Path, required=True)
    parser.add_argument("--figures", type=Path, required=True, help="JSON list: id, label, html (relative to manifest)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = bundle(args.shell.read_text(encoding="utf-8"), json.loads(args.figures.read_text(encoding="utf-8")), args.figures.parent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
