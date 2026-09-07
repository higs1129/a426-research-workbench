from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_semantic_svg.py"
CHECKER = ROOT / "scripts" / "check_semantic_svg_integrity.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *args], check=False, capture_output=True, text=True, encoding="utf-8")


def figure_model(source: str = "authoritative-data", confidence: str = "exact") -> dict:
    return {
        "figureId": "response", "profile": "90mm-single", "heightMm": 58,
        "sourceOrigin": source, "coordinateConfidence": confidence,
        "x": {"domain": [0, 10], "scale": "linear", "title": "Time", "unit": "s"},
        "y": {"domain": [-1, 1], "scale": "linear", "title": "Amplitude", "unit": "V"},
        "series": [{"id": "raw", "kind": "polyline", "label": "Raw", "points": [[0, 0], [5, 1], [10, -1]]}],
        "annotations": [],
    }


class SemanticSvgTests(unittest.TestCase):
    def render(self, model: dict, root: Path) -> tuple[Path, subprocess.CompletedProcess[str]]:
        model_path = root / "model.json"
        svg_path = root / "figure.svg"
        model_path.write_text(json.dumps(model), encoding="utf-8")
        return svg_path, run(RENDERER, str(model_path), "--output", str(svg_path))

    def test_exact_model_renders_standard_semantic_svg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            svg_path, result = self.render(figure_model(), root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            svg = ET.parse(svg_path).getroot()
            self.assertEqual(svg.get("data-role"), "scientific-figure")
            self.assertEqual(svg.get("data-coordinate-confidence"), "exact")
            self.assertEqual(svg.get("width"), "90mm")
            self.assertEqual(svg.get("height"), "58mm")
            self.assertEqual(svg.get("viewBox"), "0 0 90 58")
            self.assertEqual(svg.get("data-user-unit-mm"), "1")
            self.assertEqual(svg.get("data-physical-coordinate-system"), "mm-isomorphic")
            self.assertFalse(any(element.get("vector-effect") == "non-scaling-stroke" for element in svg.iter()))
            roles = {element.get("data-role") for element in svg.iter()}
            self.assertTrue({"figure-model", "data-series", "axes", "ticks-x", "ticks-y", "axis-title-x", "axis-title-y"}.issubset(roles))
            check = run(CHECKER, str(svg_path))
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn("awaiting user", check.stdout)
            self.assertNotIn("PASS", check.stdout)

    def test_canvas_reconstruction_must_remain_approximate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            svg_path, result = self.render(figure_model("canvas-reconstruction", "approximate"), root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(ET.parse(svg_path).getroot().get("data-coordinate-confidence"), "approximate")
            _, bad = self.render(figure_model("canvas-reconstruction", "exact"), root)
            self.assertNotEqual(bad.returncode, 0)

    def test_heatmap_keeps_raster_field_inside_vector_axes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = figure_model()
            model["series"] = []
            model["rasterField"] = {"href": "data:image/png;base64," + base64.b64encode(b"fixture").decode(), "kind": "continuous", "resampling": "bicubic", "pixelWidth": 1200, "pixelHeight": 900}
            svg_path, result = self.render(model, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            check = run(CHECKER, str(svg_path))
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            field = next(element for element in ET.parse(svg_path).getroot().iter() if element.get("data-role") == "raster-field")
            self.assertEqual(field.get("preserveAspectRatio"), "none")

    def test_scatter_and_point_line_use_half_tick_marker_diameter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = figure_model()
            model["series"] = [
                {"id": "points", "kind": "scatter", "label": "Points", "points": [[0, 0], [5, 1]]},
                {"id": "joined", "kind": "point-line", "label": "Joined", "points": [[0, -1], [5, 0], [10, 1]]},
            ]
            svg_path, result = self.render(model, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(svg_path).getroot()
            style = next(element for element in svg.iter() if element.get("data-role") == "figure-style")
            style_text = style.text or ""
            tick_size = float(re.search(r"--tick-label-size:([0-9.]+)px", style_text).group(1))
            marker_diameter = float(re.search(r"--marker-diameter:([0-9.]+)px", style_text).group(1))
            self.assertAlmostEqual(marker_diameter, tick_size * 0.5)
            markers = [element for element in svg.iter() if element.get("data-role") == "data-marker"]
            self.assertEqual(len(markers), 5)
            self.assertTrue(all(abs(float(marker.get("r")) - marker_diameter / 2) < 1e-6 for marker in markers))
            self.assertTrue(all(marker.get("data-default-size") == "true" for marker in markers))
            point_line = next(element for element in svg.iter() if element.get("data-series-kind") == "point-line")
            self.assertTrue(any(child.tag.endswith("polyline") for child in point_line))

    def test_missing_axis_semantics_stops_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = figure_model()
            del model["x"]["title"]
            _, result = self.render(model, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("x.title is required", result.stderr)

    def test_checker_rejects_broken_physical_coordinate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            svg_path, result = self.render(figure_model(), root)
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(svg_path)
            svg.getroot().set("viewBox", "0 0 1000 644")
            polyline = next(element for element in svg.getroot().iter() if element.tag.endswith("polyline"))
            polyline.set("vector-effect", "non-scaling-stroke")
            svg.write(svg_path, encoding="unicode")
            check = run(CHECKER, str(svg_path))
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("viewBox must numerically match", check.stdout)
            self.assertIn("non-scaling-stroke", check.stdout)


if __name__ == "__main__":
    unittest.main()
