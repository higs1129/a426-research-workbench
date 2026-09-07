#!/usr/bin/env python3
"""Run cheap file-integrity checks on a formal scientific-poster HTML file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class PosterParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.layout_ids: set[str] = set()
        self.duplicate_layout_ids: set[str] = set()
        self.page_found = False
        self.asset_refs: list[str] = []
        self.figures: list[dict] = []
        self._figure_stack: list[tuple[str, dict]] = []
        self._metadata_target: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        node_id = values.get("id")
        if node_id:
            if node_id in self.ids:
                self.duplicate_ids.add(node_id)
            self.ids.add(node_id)
        layout_id = values.get("data-layout-id")
        if layout_id:
            if layout_id in self.layout_ids:
                self.duplicate_layout_ids.add(layout_id)
            self.layout_ids.add(layout_id)
        if values.get("data-role") == "poster-page" and values.get("data-page-width-mm") and values.get("data-page-height-mm"):
            self.page_found = True
        if values.get("data-role") == "figure-region":
            record = {"tag": tag, "asset_class": values.get("data-asset-class", ""), "figure_id": values.get("data-figure-id", ""), "semantic_svg": False, "model": "", "roles": set(), "source_origin": "", "confidence": "", "width": "", "height": "", "viewbox": "", "unit_mm": "", "coordinate_system": "", "non_scaling_stroke": False}
            self.figures.append(record)
            self._figure_stack.append((tag, record))
        if self._figure_stack:
            record = self._figure_stack[-1][1]
            role = values.get("data-role")
            if role:
                record["roles"].add(role)
            if tag == "svg" and role == "scientific-figure":
                record["semantic_svg"] = True
                record["source_origin"] = values.get("data-source-origin", "")
                record["confidence"] = values.get("data-coordinate-confidence", "")
                record["width"] = values.get("width", "")
                record["height"] = values.get("height", "")
                record["viewbox"] = values.get("viewbox", "")
                record["unit_mm"] = values.get("data-user-unit-mm", "")
                record["coordinate_system"] = values.get("data-physical-coordinate-system", "")
            if values.get("vector-effect") == "non-scaling-stroke":
                record["non_scaling_stroke"] = True
            if tag == "metadata" and role == "figure-model":
                self._metadata_target = record
        if tag in {"img", "image", "script", "link", "object", "source"}:
            for key in ("src", "href", "data"):
                value = values.get(key, "").strip()
                if value:
                    self.asset_refs.append(value)

    def handle_data(self, data: str) -> None:
        if self._metadata_target is not None:
            self._metadata_target["model"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "metadata":
            self._metadata_target = None
        if self._figure_stack and tag == self._figure_stack[-1][0]:
            self._figure_stack.pop()


def parse_html(path: Path) -> PosterParser:
    parser = PosterParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def parse_mm(value: str) -> float | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)mm", value)
    return float(match.group(1)) if match else None


def parse_viewbox(value: str) -> tuple[float, float, float, float] | None:
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        return tuple(float(part) for part in parts)
    except ValueError:
        return None


def inspect(path: Path, approved: Path | None) -> list[str]:
    issues: list[str] = []
    raw = path.read_text(encoding="utf-8")
    if re.search(r"\b(?:NaN|Infinity|-Infinity)\b", raw):
        issues.append("non-finite numeric token in HTML")
    parser = parse_html(path)
    if not parser.page_found:
        issues.append("poster page lacks physical width/height markers")
    for value in sorted(parser.duplicate_ids):
        issues.append(f"duplicate id: {value}")
    for value in sorted(parser.duplicate_layout_ids):
        issues.append(f"duplicate data-layout-id: {value}")
    if not parser.layout_ids:
        issues.append("no production-bound data-layout-id values")
    for reference in parser.asset_refs:
        if reference.startswith(("http://", "https://")):
            issues.append(f"remote asset dependency: {reference}")
            continue
        if reference.startswith(("data:", "#", "mailto:", "javascript:")):
            continue
        candidate = (path.parent / reference.split("?", 1)[0].split("#", 1)[0]).resolve()
        if not candidate.exists():
            issues.append(f"missing local asset: {reference}")
    expected_confidence = {"authoritative-data": "exact", "inline-data-html": "exact", "canvas-reconstruction": "approximate"}
    for figure in parser.figures:
        label = figure["figure_id"] or "<missing-figure-id>"
        if not figure["figure_id"]:
            issues.append("figure region lacks data-figure-id")
        if figure["asset_class"] == "quantitative-data":
            if not figure["semantic_svg"]:
                issues.append(f"{label}: quantitative figure lacks standard inline semantic SVG")
            confidence = expected_confidence.get(figure["source_origin"])
            if confidence is None or figure["confidence"] != confidence:
                issues.append(f"{label}: source origin/confidence markers are inconsistent")
            width_mm = parse_mm(figure["width"])
            height_mm = parse_mm(figure["height"])
            box = parse_viewbox(figure["viewbox"])
            if width_mm is None or height_mm is None or box is None:
                issues.append(f"{label}: quantitative SVG lacks a millimetre viewport/viewBox")
            elif abs(box[0]) > 1e-9 or abs(box[1]) > 1e-9 or abs(box[2] - width_mm) > 1e-6 or abs(box[3] - height_mm) > 1e-6:
                issues.append(f"{label}: SVG viewBox does not match its millimetre slot")
            if figure["unit_mm"] != "1" or figure["coordinate_system"] != "mm-isomorphic":
                issues.append(f"{label}: quantitative SVG lacks millimetre-isomorphic coordinate markers")
            if figure["non_scaling_stroke"]:
                issues.append(f"{label}: non-scaling-stroke breaks physical line-width control")
            required = {"figure-model", "plot-area", "plot-box", "axes", "ticks-x", "ticks-y", "axis-title-x", "axis-title-y"}
            for role in sorted(required - figure["roles"]):
                issues.append(f"{label}: missing semantic SVG role {role}")
            try:
                model = json.loads(figure["model"])
                json.dumps(model, allow_nan=False)
            except (json.JSONDecodeError, ValueError):
                issues.append(f"{label}: embedded figure model is invalid")
    if approved is not None:
        approved_parser = parse_html(approved)
        missing = approved_parser.layout_ids - parser.layout_ids
        added = parser.layout_ids - approved_parser.layout_ids
        for value in sorted(missing):
            issues.append(f"formal poster is missing approved data-layout-id: {value}")
        for value in sorted(added):
            issues.append(f"formal poster adds unapproved data-layout-id: {value}")
    return issues


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--approved-wireframe", type=Path)
    args = parser.parse_args()
    try:
        issues = inspect(args.html.resolve(), args.approved_wireframe.resolve() if args.approved_wireframe else None)
    except OSError as exc:
        print(f"Poster integrity check failed: {exc}", file=sys.stderr)
        return 2
    if issues:
        print(f"FILE INTEGRITY FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("FILE INTEGRITY SATISFIED; awaiting user scientific, visual, and print review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
