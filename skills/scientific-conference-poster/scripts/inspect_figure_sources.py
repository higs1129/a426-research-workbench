#!/usr/bin/env python3
"""Read-only inventory of candidate scientific-figure sources."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


SUPPORTED = {
    ".ai",
    ".eps",
    ".svg",
    ".pdf",
    ".pptx",
    ".ppt",
    ".png",
    ".tif",
    ".tiff",
    ".jpg",
    ".jpeg",
    ".html",
    ".htm",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def probe_bytes(path: Path, limit: int = 16 * 1024 * 1024) -> bytes:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size <= limit:
            return handle.read()
        half = limit // 2
        start = handle.read(half)
        handle.seek(max(0, size - half))
        return start + handle.read(half)


def inspect_postscript(path: Path) -> dict:
    text = probe_bytes(path).decode("latin-1", errors="ignore")
    creator = re.search(r"^%%Creator:\s*(.+)$", text, re.MULTILINE)
    hires = re.search(r"^%%HiResBoundingBox:\s*(.+)$", text, re.MULTILINE)
    bbox = re.search(r"^%%BoundingBox:\s*(.+)$", text, re.MULTILINE)
    illustrator = "Adobe Illustrator" in text or "%AI" in text
    raster_markers = sum(text.count(token) for token in ("colorimage", "/ImageType", "BeginRaster"))
    group_markers = sum(text.count(token) for token in ("BeginLayer", "BeginGroup", "BeginObject"))
    return {
        "container": "postscript",
        "creator": creator.group(1).strip() if creator else None,
        "bounding_box": (hires or bbox).group(1).strip() if (hires or bbox) else None,
        "illustrator_metadata": illustrator,
        "raster_markers": raster_markers,
        "explicit_group_markers": group_markers,
        "source_route_candidate": "grouped-vector" if group_markers else "ungrouped-vector",
        "panel_group_readiness": "candidate" if group_markers else "not-demonstrated",
        "inspection_hint": (
            "Open a temporary copy with an Illustrator-compatible or vector-preserving tool and inspect groups, placed images, text, and clipping paths."
            if illustrator
            else "Convert a temporary copy with a vector-preserving tool and inspect objects before any eligible non-quantitative raster crop."
        ),
    }


def inspect_ai(path: Path) -> dict:
    data = probe_bytes(path)
    pdf_compatible = data.lstrip().startswith(b"%PDF-") or b"%PDF-" in data[:4096]
    if pdf_compatible:
        text = data.decode("latin-1", errors="ignore")
        layer_names = sorted(set(re.findall(r"/OC\s*/?([^\s<>\[\]()]+)", text)))
        image_objects = len(re.findall(r"/Subtype\s*/Image\b", text))
        font_objects = len(re.findall(r"/Type\s*/Font\b", text))
        return {
            "container": "pdf-compatible-ai",
            "pdf_compatible": True,
            "named_layer_hints": layer_names[:100],
            "embedded_image_object_hints": image_objects,
            "editable_text_hints": font_objects,
            "panel_group_readiness": "candidate" if layer_names else "not-demonstrated",
            "source_route_candidate": "grouped-ai" if layer_names else "ungrouped-vector",
            "inspection_hint": (
                "Inspect the PDF-compatible AI once, verify named top-level panel groups, embedded placed images, live text, and complete panel boundaries, then batch-export through one converted SVG."
            ),
        }
    result = inspect_postscript(path)
    result["pdf_compatible"] = False
    result["source_route_candidate"] = "grouped-ai" if result["explicit_group_markers"] else "ungrouped-vector"
    result["panel_group_readiness"] = (
        "candidate" if result["explicit_group_markers"] else "not-demonstrated"
    )
    result["inspection_hint"] = (
        "This AI file does not expose a PDF-compatible header. Verify grouping in a temporary copy or request a grouped SVG export; do not enter a raster route for quantitative data."
    )
    return result


def inspect_pptx(path: Path) -> dict:
    result = {
        "container": "pptx-package",
        "slides": 0,
        "media": [],
        "slide_objects": [],
        "inspection_hint": "Inspect original ppt/media assets together with slide groups, overlays, and crop settings; export the complete evidence-unit group.",
    }
    try:
        with zipfile.ZipFile(path) as package:
            names = package.namelist()
            result["media"] = sorted(name for name in names if name.startswith("ppt/media/"))
            slide_names = sorted(
                name
                for name in names
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            )
            result["slides"] = len(slide_names)
            for slide_name in slide_names:
                counts = {"pictures": 0, "groups": 0, "text_shapes": 0, "connectors": 0, "crop_rectangles": 0}
                root = ElementTree.fromstring(package.read(slide_name))
                for element in root.iter():
                    name = local_name(element.tag)
                    if name == "pic":
                        counts["pictures"] += 1
                    elif name == "grpSp":
                        counts["groups"] += 1
                    elif name == "sp":
                        counts["text_shapes"] += 1
                    elif name == "cxnSp":
                        counts["connectors"] += 1
                    elif name == "srcRect":
                        counts["crop_rectangles"] += 1
                counts["slide"] = slide_name
                result["slide_objects"].append(counts)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        result["error"] = str(exc)
    return result


def inspect_svg(path: Path) -> dict:
    counts = {"groups": 0, "images": 0, "texts": 0, "clip_paths": 0}
    try:
        tree = ElementTree.parse(path)
        root = tree.getroot()
        top_level_panels = []
        external_images = 0
        legacy_fonts = 0
        for element in root.iter():
            name = local_name(element.tag)
            if name == "g":
                counts["groups"] += 1
            elif name == "image":
                counts["images"] += 1
            elif name == "text":
                counts["texts"] += 1
            elif name == "clipPath":
                counts["clip_paths"] += 1
            elif name in {"font", "glyph", "missing-glyph"}:
                legacy_fonts += 1
            if name == "image":
                href = element.get("href") or element.get("{http://www.w3.org/1999/xlink}href") or ""
                if href and not href.startswith("data:"):
                    external_images += 1
        for child in list(root):
            if local_name(child.tag) != "g":
                continue
            panel_id = child.get("data-panel-id") or child.get("id")
            if panel_id:
                top_level_panels.append(panel_id)
        return {
            "container": "svg",
            "objects": counts,
            "top_level_panel_groups": top_level_panels,
            "panel_group_readiness": "ready" if top_level_panels else "not-demonstrated",
            "external_image_references": external_images,
            "legacy_svg_font_elements": legacy_fonts,
            "source_route_candidate": "grouped-vector" if top_level_panels else "ungrouped-vector",
            "inspection_hint": "Inspect relevant groups and referenced definitions; keep required overlays with the target group.",
        }
    except (OSError, ElementTree.ParseError) as exc:
        return {"container": "svg", "error": str(exc)}


class FigureHtmlInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inline_svg_count = 0
        self.json_script_count = 0
        self.semantic_series_ids: set[str] = set()
        self.external_dependencies: set[str] = set()
        self.renderer_version = False
        self.provenance = False
        self._json_depth = 0
        self._json_payloads: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "svg":
            self.inline_svg_count += 1
        if tag == "script" and values.get("type", "").lower() in {
            "application/json",
            "application/ld+json",
        }:
            self.json_script_count += 1
            self._json_depth += 1
        series_id = values.get("data-series-id") or values.get("data-trace-id")
        if series_id:
            self.semantic_series_ids.add(series_id)
        if "data-renderer-version" in values or "data-figure-renderer" in values:
            self.renderer_version = True
        if "data-provenance" in values or "data-source-provenance" in values:
            self.provenance = True
        dependency_attributes = ["src"]
        if tag in {"image", "use", "link"}:
            dependency_attributes.append("href")
        if tag == "object":
            dependency_attributes.append("data")
        for key in dependency_attributes:
            value = values.get(key, "").strip()
            if value and not value.startswith(("#", "data:", "javascript:")):
                self.external_dependencies.add(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_depth:
            self._json_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._json_depth and data.strip():
            self._json_payloads.append(data)


def inspect_html(path: Path) -> dict:
    try:
        parser = FigureHtmlInspector()
        parser.feed(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return {"container": "html", "error": str(exc)}

    valid_json_payloads = 0
    semantic_json = False
    for payload in parser._json_payloads:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        valid_json_payloads += 1
        serialized = json.dumps(parsed, ensure_ascii=False).lower()
        if any(token in serialized for token in ('"data"', '"series"', '"units"', '"axes"')):
            semantic_json = True
    ready = all(
        (
            parser.inline_svg_count > 0,
            valid_json_payloads > 0,
            semantic_json,
            bool(parser.semantic_series_ids),
            parser.renderer_version,
            parser.provenance,
            not parser.external_dependencies,
        )
    )
    return {
        "container": "self-contained-html-candidate",
        "inline_svg_count": parser.inline_svg_count,
        "json_script_count": parser.json_script_count,
        "valid_json_payloads": valid_json_payloads,
        "semantic_json_hints": semantic_json,
        "semantic_series_ids": sorted(parser.semantic_series_ids),
        "renderer_version_declared": parser.renderer_version,
        "provenance_declared": parser.provenance,
        "external_dependencies": sorted(parser.external_dependencies),
        "inline_data_readiness": "ready" if ready else "incomplete",
        "source_route_candidate": "inline-data-html" if ready else "html-reference-only",
        "inspection_hint": (
            "Qualified inline-data HTML must keep authoritative data, units/axes semantics, stable series-to-SVG ids, renderer version, provenance, and the SVG view in one self-contained file."
        ),
    }


def inspect_candidate(path: Path, root: Path) -> dict:
    suffix = path.suffix.lower()
    record = {
        "path": str(path.relative_to(root)),
        "extension": suffix,
        "bytes": path.stat().st_size,
    }
    if suffix == ".pptx":
        record.update(inspect_pptx(path))
    elif suffix == ".ppt":
        record.update(
            {
                "container": "legacy-powerpoint",
                "inspection_hint": "Convert a temporary copy to PPTX or export selected object groups through PowerPoint; request PPTX if fidelity changes.",
            }
        )
    elif suffix == ".ai":
        record.update(inspect_ai(path))
    elif suffix == ".eps":
        record.update(inspect_postscript(path))
    elif suffix == ".svg":
        record.update(inspect_svg(path))
    elif suffix in {".html", ".htm"}:
        record.update(inspect_html(path))
    elif suffix == ".pdf":
        record.update(
            {
                "container": "pdf",
                "inspection_hint": "Determine whether the PDF is vector and inspect embedded images, text, paths, and overlays before page cropping.",
            }
        )
    else:
        record.update(
            {
                "container": "raster",
                "inspection_hint": "Prefer a matching standalone or editable source; a composite raster crop is eligible only for non-quantitative image evidence through the documented exception gate.",
            }
        )
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Authorized directory or single file to inspect")
    parser.add_argument("--stem", help="Keep candidates whose filename stem contains this text")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        print(json.dumps({"error": f"Path does not exist: {root}"}, ensure_ascii=False, indent=2))
        return 2

    base = root if root.is_dir() else root.parent
    paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    stem_filter = args.stem.casefold() if args.stem else None
    candidates = []
    for path in sorted(paths, key=lambda item: str(item).casefold()):
        if path.suffix.lower() not in SUPPORTED:
            continue
        if stem_filter and stem_filter not in path.stem.casefold():
            continue
        candidates.append(inspect_candidate(path, base))

    payload = {
        "root": str(root),
        "read_only": True,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "note": "Structural clues do not establish the scientifically correct target panel.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
