#!/usr/bin/env python3
"""Run cheap structural integrity checks on a standard semantic scientific SVG."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


URL_REF = re.compile(r"url\(\s*#([^\s)]+)\s*\)")
NUMBER = re.compile(r"(?<![A-Za-z])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
REQUIRED_ROLES = {"scientific-figure", "figure-model", "plot-area", "plot-box", "axes", "ticks-x", "ticks-y", "axis-title-x", "axis-title-y"}
REQUIRED_CSS = {"--figure-font-family", "--axis-label-size", "--tick-label-size", "--annotation-size", "--data-line-width", "--axis-line-width", "--tick-length"}
PROFILE_RANGES = {"90mm-single": (85, 90), "185mm-double": (180, 185), "185mm-composite": (180, 185)}


def millimetres(value: str) -> float | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)mm", value)
    return float(match.group(1)) if match else None


def viewbox(value: str) -> tuple[float, float, float, float] | None:
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        result = tuple(float(part) for part in parts)
    except ValueError:
        return None
    return result if all(math.isfinite(item) for item in result) else None


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def inspect(path: Path) -> list[str]:
    issues: list[str] = []
    raw = path.read_text(encoding="utf-8")
    if re.search(r"\b(?:NaN|Infinity|-Infinity)\b", raw):
        issues.append("non-finite numeric token")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [f"cannot parse SVG: {exc}"]
    if root.get("data-role") != "scientific-figure":
        issues.append("root requires data-role=scientific-figure")
    if root.get("preserveAspectRatio") == "none":
        issues.append("whole SVG cannot use preserveAspectRatio=none")
    profile = root.get("data-profile", "")
    width_mm = millimetres(root.get("width", ""))
    height_mm = millimetres(root.get("height", ""))
    box = viewbox(root.get("viewBox", ""))
    if profile not in PROFILE_RANGES or width_mm is None:
        issues.append("standard profile and millimetre width are required")
    elif not PROFILE_RANGES[profile][0] <= width_mm <= PROFILE_RANGES[profile][1]:
        issues.append("SVG width is outside the selected standard profile")
    if height_mm is None or box is None:
        issues.append("millimetre height and a four-number viewBox are required")
    elif width_mm is not None and (abs(box[0]) > 1e-9 or abs(box[1]) > 1e-9 or abs(box[2] - width_mm) > 1e-6 or abs(box[3] - height_mm) > 1e-6):
        issues.append("viewBox must numerically match the millimetre viewport (1 user unit = 1 mm)")
    if root.get("data-user-unit-mm") != "1" or root.get("data-physical-coordinate-system") != "mm-isomorphic":
        issues.append("millimetre-isomorphic coordinate markers are required")
    origin = root.get("data-source-origin")
    confidence = root.get("data-coordinate-confidence")
    expected = {"authoritative-data": "exact", "inline-data-html": "exact", "canvas-reconstruction": "approximate"}.get(origin)
    if expected is None or confidence != expected:
        issues.append("source origin and coordinate confidence are inconsistent")

    ids: set[str] = set()
    roles: set[str] = set()
    references: list[str] = []
    style_text = ""
    metadata_text = None
    text_count = 0
    series_count = 0
    for element in root.iter():
        name = local_name(element.tag)
        element_id = element.get("id")
        if element_id:
            if element_id in ids:
                issues.append(f"duplicate id: {element_id}")
            ids.add(element_id)
        role = element.get("data-role")
        if role:
            roles.add(role)
        if name in {"font", "glyph", "missing-glyph", "script"}:
            issues.append(f"forbidden SVG element: {name}")
        if element.get("vector-effect") == "non-scaling-stroke":
            issues.append("non-scaling-stroke breaks the physical stroke-width contract")
        if name in {"text", "tspan"}:
            text_count += 1
        if role == "data-series":
            series_count += 1
        if role == "figure-model":
            metadata_text = element.text or ""
        if name == "style":
            style_text += element.text or ""
        for key, value in element.attrib.items():
            if key.lower().startswith("on"):
                issues.append(f"event handler is forbidden: {key}")
            references.extend(URL_REF.findall(value))
            if local_name(key) in {"href", "src"}:
                if value.startswith("#"):
                    references.append(value[1:])
                elif not value.startswith("data:"):
                    issues.append(f"external dependency: {value}")
            for match in NUMBER.findall(value):
                try:
                    if not math.isfinite(float(match)):
                        issues.append(f"non-finite attribute value: {value}")
                except ValueError:
                    pass
        if name == "image" and element.get("preserveAspectRatio") == "none":
            if role != "raster-field":
                issues.append("only data-role=raster-field may use preserveAspectRatio=none")
            if not (element.get("href", "").startswith("data:image/") and element.get("data-pixel-width") and element.get("data-pixel-height")):
                issues.append("raster field lacks embedded image or pixel dimensions")
    for reference in references:
        if reference not in ids:
            issues.append(f"unresolved local reference: {reference}")
    for reference in URL_REF.findall(style_text):
        if reference not in ids:
            issues.append(f"unresolved local style reference: {reference}")
    if re.search(r"url\(\s*['\"]?(?:https?://|file:|[A-Za-z]:[/\\])", style_text, re.IGNORECASE):
        issues.append("external dependency in SVG style")
    for role in sorted(REQUIRED_ROLES - roles):
        issues.append(f"missing required role: {role}")
    if text_count == 0:
        issues.append("no live text remains")
    if series_count == 0 and "raster-field" not in roles:
        issues.append("no semantic data series or raster field remains")
    for token in sorted(REQUIRED_CSS):
        if token not in style_text:
            issues.append(f"missing CSS variable: {token}")
    if 'Calibri' not in style_text or 'Microsoft YaHei' not in style_text or 'sans-serif' not in style_text:
        issues.append("fallback font stack is incomplete")
    if metadata_text is None:
        issues.append("figure model metadata is missing")
    else:
        try:
            model = json.loads(metadata_text)
            json.dumps(model, allow_nan=False)
        except (json.JSONDecodeError, ValueError) as exc:
            issues.append(f"figure model is invalid: {exc}")
    return issues


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args()
    try:
        issues = inspect(args.svg.resolve())
    except OSError as exc:
        print(f"File integrity check failed: {exc}", file=sys.stderr)
        return 2
    if issues:
        print(f"FILE INTEGRITY FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("FILE INTEGRITY SATISFIED; awaiting user scientific and visual review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
