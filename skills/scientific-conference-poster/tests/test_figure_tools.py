from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = SKILL_ROOT.parents[1]
INSPECTOR = SKILL_ROOT / "scripts" / "inspect_figure_sources.py"
EXTRACTOR = SKILL_ROOT / "scripts" / "extract_grouped_panels.py"
ADAPTER = SKILL_ROOT / "scripts" / "adapt_semantic_svg_for_slot.py"
CHECKER = SKILL_ROOT / "scripts" / "check_poster_integrity.py"
RENDERER = WORKBENCH / "skills" / "scientific-plotting" / "scripts" / "render_semantic_svg.py"


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *args], check=False, capture_output=True, text=True, encoding="utf-8")


def figure_model(source: str = "authoritative-data", confidence: str = "exact") -> dict:
    return {
        "figureId": "panel-e", "profile": "90mm-single", "heightMm": 60,
        "sourceOrigin": source, "coordinateConfidence": confidence,
        "x": {"domain": [0, 25], "scale": "linear", "title": "Frequency", "unit": "GHz"},
        "y": {"domain": [-120, -40], "scale": "linear", "title": "Power", "unit": "dBm"},
        "series": [{"id": "trace", "kind": "polyline", "label": "Measured", "points": [[0, -80], [12, -55], [25, -100]]}],
        "annotations": [{"x": 12, "y": -55, "text": "Locked"}],
    }


class FigureSourceInspectorTests(unittest.TestCase):
    def test_inventory_detects_pptx_objects_and_eps_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "FIG_2.eps").write_text("%!PS-Adobe-3.0 EPSF-3.0\n%%Creator: Adobe Illustrator(R) 28.0\n%AI5_BeginLayer\n/ImageType 1 def\n", encoding="latin-1")
            pptx = root / "figure-source.pptx"
            slide_xml = '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:grpSp/><p:pic><p:blipFill><a:srcRect l="1"/></p:blipFill></p:pic></p:spTree></p:cSld></p:sld>'
            with zipfile.ZipFile(pptx, "w") as package:
                package.writestr("ppt/slides/slide1.xml", slide_xml)
                package.writestr("ppt/media/image1.png", b"test")
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            result = run_script(INSPECTOR, str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, sorted(path.relative_to(root) for path in root.rglob("*")))
            by_name = {item["path"]: item for item in json.loads(result.stdout)["candidates"]}
            self.assertTrue(by_name["FIG_2.eps"]["illustrator_metadata"])
            self.assertEqual(by_name["figure-source.pptx"]["slide_objects"][0]["groups"], 1)

    def test_inventory_recognizes_qualified_html_and_grouped_svg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "figure.html").write_text('<body data-renderer-version="1" data-provenance="raw"><script type="application/json">{"series":[1],"axes":{"x":{"units":"Hz"}}}</script><svg><g data-series-id="a"></g></svg></body>', encoding="utf-8")
            (root / "grouped.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><g id="panel-a"/></svg>', encoding="utf-8")
            result = run_script(INSPECTOR, str(root))
            by_name = {item["path"]: item for item in json.loads(result.stdout)["candidates"]}
            self.assertEqual(by_name["figure.html"]["inline_data_readiness"], "ready")
            self.assertEqual(by_name["grouped.svg"]["panel_group_readiness"], "ready")


class GroupedPanelExtractionTests(unittest.TestCase):
    def test_extracts_named_panels_once_and_reuses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            groups = "".join(f'<g id="panel-{index}"><path d="M0 {index}L10 {index}"/></g>' for index in range(3))
            (root / "source.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{groups}</svg>', encoding="utf-8")
            manifest = {"converted_svg": "source.svg", "panels": [{"panel_id": f"panel-{index}", "group_id": f"panel-{index}", "viewBox": "0 0 10 10", "output": f"panel-{index}.svg"} for index in range(3)]}
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "out"
            first = run_script(EXTRACTOR, str(path), "--output-dir", str(output))
            second = run_script(EXTRACTOR, str(path), "--output-dir", str(output))
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertTrue(all(item["status"] == "cached" for item in json.loads(second.stdout)["panels"]))


class PosterSemanticSvgTests(unittest.TestCase):
    def render(self, root: Path) -> Path:
        model_path = root / "model.json"
        svg_path = root / "standard.svg"
        model_path.write_text(json.dumps(figure_model()), encoding="utf-8")
        result = run_script(RENDERER, str(model_path), "--output", str(svg_path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return svg_path

    def test_slot_adapter_reflows_semantic_geometry_and_preserves_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            svg_path = self.render(root)
            output = root / "adapted.svg"
            result = run_script(ADAPTER, str(svg_path), "--output", str(output), "--width-mm", "310", "--height-mm", "165", "--base-mm", "12", "--style", "tickLabelSize=26,axisLabelSize=30")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            svg = ET.parse(output).getroot()
            self.assertEqual(svg.get("data-poster-adaptation"), "semantic-reflow")
            self.assertEqual(svg.get("data-coordinate-confidence"), "exact")
            self.assertEqual(svg.get("width"), "310mm")
            self.assertEqual(svg.get("height"), "165mm")
            self.assertEqual(svg.get("viewBox"), "0 0 310 165")
            self.assertEqual(svg.get("data-user-unit-mm"), "1")
            self.assertEqual(svg.get("data-poster-base-mm"), "12")
            self.assertFalse(any(element.get("vector-effect") == "non-scaling-stroke" for element in svg.iter()))
            model_node = next(item for item in svg.iter() if item.get("data-role") == "figure-model")
            adaptation = json.loads(model_node.text)["posterAdaptation"]
            self.assertEqual(adaptation["style"]["tickLabelSize"], 26)
            self.assertAlmostEqual(adaptation["style"]["annotationSize"], 9.84)
            self.assertEqual(adaptation["coordinateSystem"]["mmPerUserUnit"], 1)

    def test_poster_checker_compares_layout_membership_without_claiming_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            svg = self.render(root).read_text(encoding="utf-8")
            wireframe = root / "wireframe.html"
            formal = root / "formal.html"
            wireframe.write_text('<main data-role="poster-page" data-page-width-mm="900" data-page-height-mm="1200" data-layout-id="page"><figure data-layout-id="slot" data-role="figure-region" data-figure-id="panel-e" data-asset-class="quantitative-data"></figure></main>', encoding="utf-8")
            formal.write_text(f'<main data-role="poster-page" data-page-width-mm="900" data-page-height-mm="1200" data-layout-id="page"><figure data-layout-id="slot" data-role="figure-region" data-figure-id="panel-e" data-asset-class="quantitative-data">{svg}</figure></main>', encoding="utf-8")
            result = run_script(CHECKER, str(formal), "--approved-wireframe", str(wireframe))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("awaiting user", result.stdout)
            self.assertNotIn("PASS", result.stdout)

    def test_checker_rejects_layout_membership_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wireframe = root / "wireframe.html"
            formal = root / "formal.html"
            wireframe.write_text('<main data-role="poster-page" data-page-width-mm="1" data-page-height-mm="1" data-layout-id="page"><div data-layout-id="slot"></div></main>', encoding="utf-8")
            formal.write_text('<main data-role="poster-page" data-page-width-mm="1" data-page-height-mm="1" data-layout-id="page"><div data-layout-id="new-slot"></div></main>', encoding="utf-8")
            result = run_script(CHECKER, str(formal), "--approved-wireframe", str(wireframe))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing approved data-layout-id: slot", result.stdout)

    def test_poster_checker_rejects_non_isomorphic_quantitative_svg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            svg = self.render(root).read_text(encoding="utf-8").replace('viewBox="0 0 90 60"', 'viewBox="0 0 1000 667"')
            svg = svg.replace("<polyline ", '<polyline vector-effect="non-scaling-stroke" ', 1)
            formal = root / "formal.html"
            formal.write_text(f'<main data-role="poster-page" data-page-width-mm="900" data-page-height-mm="1200" data-layout-id="page"><figure data-layout-id="slot" data-role="figure-region" data-figure-id="panel-e" data-asset-class="quantitative-data">{svg}</figure></main>', encoding="utf-8")
            result = run_script(CHECKER, str(formal))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("viewBox does not match", result.stdout)
            self.assertIn("non-scaling-stroke", result.stdout)


if __name__ == "__main__":
    unittest.main()
