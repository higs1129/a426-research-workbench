#!/usr/bin/env python3
"""Compare stable structural facts for two GDS/OASIS files using KLayout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import klayout.db as kdb
from geometry_checks import compare_files


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
    parser.add_argument("--top-cell", help="Shared top-cell name for geometry XOR")
    parser.add_argument("--layer", action="append", default=[], help="Protected layer/datatype for XOR, e.g. 10/0; repeat as needed")
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
    comparison["status"] = "inventory_only_not_geometry_verification"
    if args.layer or args.top_cell:
        if not args.layer or not args.top_cell:
            parser.error("Geometry comparison requires both --top-cell and at least one --layer")
        try:
            pairs = [tuple(int(value) for value in item.split("/")) for item in args.layer]
            if any(len(pair) != 2 for pair in pairs):
                raise ValueError("use layer/datatype")
            comparison["geometry"] = compare_files(args.reference, args.candidate, args.top_cell, pairs)
        except ValueError as exc:
            parser.error(str(exc))
        comparison["status"] = "selected_mask_geometry_xor"
        comparison["ok"] = comparison["geometry"]["ok"]
    else:
        comparison["ok"] = comparison["same_top_cell_names"] and comparison["same_layer_inventory"]
    payload = json.dumps(comparison, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0 if comparison["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
