#!/usr/bin/env python3
"""Batch-extract explicitly named SVG panel groups from one converted source."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
from xml.etree import ElementTree


SVG_NS = "http://www.w3.org/2000/svg"
ElementTree.register_namespace("", SVG_NS)


class ExtractionError(ValueError):
    pass


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def load_manifest(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionError(f"cannot read manifest: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("panels"), list):
        raise ExtractionError("manifest must be an object with a panels array")
    return payload


def resolve_source(manifest_path: Path, manifest: dict) -> Path:
    value = manifest.get("converted_svg") or manifest.get("source")
    if not isinstance(value, str) or not value.strip():
        raise ExtractionError("manifest requires converted_svg or source")
    source = (manifest_path.parent / value).resolve()
    if source.suffix.lower() != ".svg":
        raise ExtractionError(
            "batch extraction accepts one already converted structured SVG; convert AI/PDF/EPS once before this step"
        )
    if not source.is_file():
        raise ExtractionError(f"converted SVG not found: {source}")
    return source


def parse_viewbox(value: object) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    if not isinstance(value, str):
        raise ExtractionError("each panel requires an explicit viewBox")
    parts = value.replace(",", " ").split()
    if len(parts) != 4:
        raise ExtractionError(f"invalid viewBox: {value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise ExtractionError(f"invalid viewBox: {value}") from exc
    if numbers[2] <= 0 or numbers[3] <= 0:
        raise ExtractionError(f"viewBox width and height must be positive: {value}")
    return " ".join(parts)


def safe_output_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtractionError("each panel requires an output filename")
    candidate = Path(value)
    if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.suffix.lower() != ".svg":
        raise ExtractionError(f"panel output must be one relative .svg filename: {value}")
    return candidate.name


def extract(manifest_path: Path, output_dir: Path) -> dict:
    started = time.perf_counter()
    manifest = load_manifest(manifest_path)
    source = resolve_source(manifest_path, manifest)
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    try:
        root = ElementTree.fromstring(source_bytes)
    except ElementTree.ParseError as exc:
        raise ExtractionError(f"cannot parse converted SVG: {exc}") from exc
    if local_name(root.tag) != "svg":
        raise ExtractionError("converted source root is not <svg>")

    groups: dict[str, ElementTree.Element] = {}
    for element in root.iter():
        if local_name(element.tag) != "g":
            continue
        group_id = element.get("data-panel-id") or element.get("id")
        if group_id and group_id not in groups:
            groups[group_id] = element

    if not groups:
        raise ExtractionError("converted SVG has no named panel groups")
    output_dir.mkdir(parents=True, exist_ok=True)
    common_children = [
        child for child in list(root) if local_name(child.tag) in {"defs", "style", "metadata"}
    ]
    records = []
    seen_outputs: set[str] = set()
    for entry in manifest["panels"]:
        if not isinstance(entry, dict):
            raise ExtractionError("every panel entry must be an object")
        panel_id = entry.get("panel_id")
        group_id = entry.get("group_id") or panel_id
        if not isinstance(panel_id, str) or not panel_id.strip():
            raise ExtractionError("each panel requires panel_id")
        if not isinstance(group_id, str) or group_id not in groups:
            raise ExtractionError(f"panel {panel_id}: named group not found: {group_id}")
        output_name = safe_output_name(entry.get("output"))
        if output_name.casefold() in seen_outputs:
            raise ExtractionError(f"duplicate panel output: {output_name}")
        seen_outputs.add(output_name.casefold())
        viewbox = parse_viewbox(entry.get("viewBox"))
        key_source = json.dumps(
            {"source_hash": source_hash, "panel_id": panel_id, "group_id": group_id, "viewBox": viewbox},
            sort_keys=True,
        ).encode("utf-8")
        extraction_key = hashlib.sha256(key_source).hexdigest()
        output_path = output_dir / output_name

        if output_path.is_file():
            try:
                existing_root = ElementTree.parse(output_path).getroot()
                if existing_root.get("data-extraction-key") == extraction_key:
                    records.append({"panel_id": panel_id, "output": str(output_path), "status": "cached"})
                    continue
            except (OSError, ElementTree.ParseError):
                pass

        panel_root = ElementTree.Element(
            f"{{{SVG_NS}}}svg",
            {
                "viewBox": viewbox,
                "preserveAspectRatio": "xMidYMid meet",
                "data-panel-id": panel_id,
                "data-source-sha256": source_hash,
                "data-extraction-key": extraction_key,
            },
        )
        for child in common_children:
            panel_root.append(copy.deepcopy(child))
        panel_root.append(copy.deepcopy(groups[group_id]))
        output_path.write_text(
            ElementTree.tostring(panel_root, encoding="unicode", short_empty_elements=True) + "\n",
            encoding="utf-8",
        )
        records.append({"panel_id": panel_id, "output": str(output_path), "status": "extracted"})

    return {
        "scope": "grouped-panel-batch-extraction",
        "source": str(source),
        "source_sha256": source_hash,
        "panel_count": len(records),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "panels": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON manifest for one converted SVG and all target panels")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Explicit isolated output directory; use a temporary directory unless reusable SVG sidecars were requested",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    try:
        result = extract(args.manifest.resolve(), args.output_dir.resolve())
    except (ExtractionError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "satisfied", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
