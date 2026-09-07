#!/usr/bin/env python3
"""Compare stable structural facts for two GDS/OASIS files using KLayout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import klayout.db as kdb


def summarize(path: Path) -> dict[str, Any]:
    layout = kdb.Layout()
    layout.read(str(path))
    layers = []
    for layer_index in layout.layer_indexes():
        info = layout.get_info(layer_index)
        stored_shapes = 0
        for cell in layout.each_cell():
            stored_shapes += cell.shapes(layer_index).size()
        layers.append({"layer": info.layer, "datatype": info.datatype, "stored_shapes": stored_shapes})
    tops = []
    for cell in layout.top_cells():
        bbox = cell.dbbox()
        tops.append(
            {
                "name": cell.name,
                "bbox_um": [bbox.left, bbox.bottom, bbox.right, bbox.top],
            }
        )
    return {
        "path": str(path),
        "dbu_um": layout.dbu,
        "cell_count": layout.cells(),
        "top_cells": tops,
        "layers": sorted(layers, key=lambda item: (item["layer"], item["datatype"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        reference = summarize(args.reference)
        candidate = summarize(args.candidate)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    comparison = {
        "ok": True,
        "reference": reference,
        "candidate": candidate,
        "same_top_cell_names": [item["name"] for item in reference["top_cells"]]
        == [item["name"] for item in candidate["top_cells"]],
        "same_layer_inventory": reference["layers"] == candidate["layers"],
    }
    payload = json.dumps(comparison, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
