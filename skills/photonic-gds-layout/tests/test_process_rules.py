"""Synthetic process regressions; no research geometry or files are accessed."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

import klayout.db as kdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from process_rules import (check_field_containment, dimension_label, format_nm_as_um,
                           layers_for_writefield, load_profile, resolve_process_defaults, validate_annotation_cell, validate_annotation_geometry,
                           validate_layer_assignment, validate_pad_groups,
                           validate_writefields, writefield_boxes)


class ProcessRulesTests(unittest.TestCase):
    def setUp(self):
        self.layout = kdb.Layout()
        self.layout.dbu = 0.001
        self.cell = self.layout.create_cell("TEST")
        self.layer = self.layout.layer(30, 0)
        self.fields = writefield_boxes([(0, 0), (500, 0)], 500, self.layout.dbu)

    def codes(self, findings):
        return {item.code for item in findings}

    def test_only_exposure_layers_change_datatype(self):
        small, large = layers_for_writefield(500), layers_for_writefield(1000.0)
        self.assertEqual(small["sin"], (1, 0))
        self.assertEqual(large["optical_text"], (1, 1))
        self.assertEqual(large["writefield"], (30, 1))
        for role in load_profile()["fixed_layers"]:
            self.assertEqual(small[role], large[role])
        self.assertIn("wrong_layer", self.codes(validate_layer_assignment("electrode", (10, 1), 1000)))
        with self.assertRaises(ValueError):
            layers_for_writefield(750)

    def multi_group_spec(self):
        return {"process": {"profile": "sin-user-process", "exposure_groups": [
                    {"id": "main", "writefield_size_um": 500},
                    {"id": "large", "writefield_size_um": 1000}],
                "layer_roles": {"device_large": "sin", "fields_large": "writefield"},
                "layer_exposure_groups": {"device": "main", "device_large": "large", "fields_large": "large"}},
                "layers": {"device": [1, 0], "device_large": None, "fields_large": None,
                           "electrode": [10, 0], "die": [20, 0]}}

    def test_multi_group_explicit_aliases_resolve_without_changing_fixed_layers(self):
        spec = self.multi_group_spec()
        result = resolve_process_defaults(spec)
        self.assertEqual(result["layers"], {"device": [1, 0], "device_large": [1, 1],
                                          "fields_large": [30, 1], "electrode": [10, 0], "die": [20, 0]})
        self.assertIsNone(spec["layers"]["device_large"])
        single = {"process": {"profile": "sin-user-process", "exposure_groups": [
                        {"id": "main", "writefield_size_um": 1000}]},
                  "layers": {"device": None, "electrode": None}}
        self.assertEqual(resolve_process_defaults(single)["layers"], {"device": [1, 1], "electrode": [10, 0]})

    def test_multi_group_rejects_wrong_fixed_or_exposure_layers(self):
        for role in load_profile()["fixed_layers"]:
            with self.subTest(fixed_role=role):
                spec = self.multi_group_spec()
                expected = load_profile()["fixed_layers"][role]
                spec["layers"][role] = [expected[0], 1]
                with self.assertRaisesRegex(ValueError, "conflicts with exposure profile"):
                    resolve_process_defaults(spec)
        for logical, wrong_pair in (("device", [10, 1]), ("device_large", [1, 0]), ("fields_large", [30, 0])):
            with self.subTest(logical=logical):
                spec = self.multi_group_spec()
                spec["layers"][logical] = wrong_pair
                with self.assertRaisesRegex(ValueError, "conflicts with exposure profile"):
                    resolve_process_defaults(spec)

    def test_multi_group_requires_unambiguous_exposure_role_and_ownership(self):
        for missing in ("device", "device_large", "fields_large"):
            with self.subTest(missing=missing):
                spec = self.multi_group_spec()
                del spec["process"]["layer_exposure_groups"][missing]
                with self.assertRaisesRegex(ValueError, "requires explicit layer_exposure_groups"):
                    resolve_process_defaults(spec)
        spec = self.multi_group_spec()
        spec["process"]["layer_exposure_groups"]["device"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Unknown exposure group"):
            resolve_process_defaults(spec)
        spec = self.multi_group_spec()
        del spec["process"]["layer_roles"]["device_large"]
        with self.assertRaisesRegex(ValueError, "requires an existing exposure-layer role"):
            resolve_process_defaults(spec)
        spec = self.multi_group_spec()
        spec["process"]["layer_roles"]["device"] = "electrode"
        with self.assertRaisesRegex(ValueError, "Cannot redefine canonical layer role"):
            resolve_process_defaults(spec)
        spec = self.multi_group_spec()
        del spec["process"]["layer_roles"]["device_large"]
        del spec["process"]["layer_exposure_groups"]["device_large"]
        spec["layers"]["device_large"] = [1, 1]
        with self.assertRaisesRegex(ValueError, "requires an explicit layer_roles"):
            resolve_process_defaults(spec)

    def test_dimension_labels_preserve_small_scan_differences(self):
        self.assertEqual(dimension_label("Dfi", 900), "Dfi .9um")
        self.assertEqual(format_nm_as_um(950), ".95um")
        self.assertEqual(format_nm_as_um("950.001"), ".950001um")
        self.assertEqual(format_nm_as_um(1000), "1um")
        self.assertEqual(format_nm_as_um(0), "0um")
        with self.assertRaises(ValueError):
            dimension_label("Radius", 900)

    def test_deduplicate_without_merging_adjacent_fields(self):
        boxes = writefield_boxes([(0, 0), (0, 0), (500, 0)], 500, .001)
        self.assertEqual(len(boxes), 2)
        for box in boxes:
            self.cell.shapes(self.layer).insert(box)
        self.assertEqual(validate_writefields(self.cell, self.layer, self.fields), [])

    def test_hollow_frame_and_merged_fields_fail(self):
        outer = kdb.Polygon(self.fields[0])
        outer.insert_hole(kdb.Box(10, 10, 499990, 499990))
        self.cell.shapes(self.layer).insert(outer)
        self.assertIn("writefield_not_solid_rectangle", self.codes(validate_writefields(self.cell, self.layer, self.fields)))
        self.cell.shapes(self.layer).clear()
        self.cell.shapes(self.layer).insert(kdb.Box(0, 0, 1000000, 500000))
        self.assertIn("writefield_mismatch", self.codes(validate_writefields(self.cell, self.layer, self.fields)))

    def test_duplicate_instances_are_detected(self):
        child = self.layout.create_cell("FIELD")
        child.shapes(self.layer).insert(self.fields[0])
        for unused in range(2):
            self.cell.insert(kdb.CellInstArray(child.cell_index(), kdb.Trans()))
        self.assertIn("duplicate_writefield", self.codes(validate_writefields(self.cell, self.layer, [self.fields[0]])))

    def test_path_frame_is_rejected(self):
        self.cell.shapes(self.layer).insert(kdb.Path([kdb.Point(0, 0), kdb.Point(500000, 0)], 100))
        self.assertIn("writefield_non_polygon", self.codes(validate_writefields(self.cell, self.layer, self.fields)))

    def test_field_boundary_must_be_representable(self):
        with self.assertRaises(ValueError):
            writefield_boxes([(0.0005, 0)], 500, .001)

    def test_fields_reject_nonfinite_and_overflow_before_integer_conversion(self):
        cases = [([(float("nan"), 0)], 500, .001),
                 ([(0, float("inf"))], 500, .001),
                 ([(0, 0)], 500, float("nan")),
                 ([(0, 0)], float("nan"), .001),
                 ([(3000000, 0)], 500, .001),
                 ([(-1500000, 0), (1500000, 0)], 500, .001)]
        for origins, size, dbu in cases:
            with self.subTest(origins=origins, size=size, dbu=dbu):
                with self.assertRaises(ValueError):
                    writefield_boxes(origins, size, dbu)

    def test_saved_gds_readback_checks_fields_and_actual_text(self):
        for box in self.fields:
            self.cell.shapes(self.layer).insert(box)
        annotation = self.layout.create_cell("OPTICAL_LABEL")
        annotation.shapes(self.layout.layer(1, 0)).insert(kdb.Text("R 60um", kdb.Trans()))
        # Test artifacts remain under this Skill's tests directory and are removed.
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = str(Path(directory) / "synthetic.gds")
            self.layout.write(path)
            actual = kdb.Layout()
            actual.read(path)
            self.assertEqual(validate_writefields(actual.cell("TEST"), actual.layer(30, 0), self.fields), [])
            result = validate_annotation_cell(actual.cell("OPTICAL_LABEL"), "optical", 1000)
            self.assertIn("wrong_layer", self.codes(result))
            self.assertIn("annotation_not_polygon", self.codes(result))

    def test_full_width_crossing_is_warning_not_hard_failure(self):
        # Centerline x=499.9 um lies in left field; the 0.4 um width straddles it.
        region = kdb.Region(kdb.Box(499700, 1000, 500100, 2000))
        result = check_field_containment(region, "bend", (1, 0), self.fields)
        self.assertEqual([item.severity for item in result], ["warning"])
        result = check_field_containment(region, "bend", (1, 0), self.fields, "Only feasible route after alternatives")
        self.assertIn("Accepted exception", result[0].message)
        self.assertEqual(check_field_containment(region, "heater", (10, 0), self.fields), [])

    def test_annotation_wrong_datatype_text_and_touch_are_detected(self):
        letters = kdb.Region(kdb.Box(100, 100, 200, 200))
        structure = kdb.Region(kdb.Box(200, 100, 300, 200))
        result = validate_annotation_geometry(letters, (1, 0), "optical", 1000,
                                              has_text_or_path=True, forbidden_geometry=structure)
        self.assertEqual(self.codes(result), {"wrong_layer", "annotation_not_polygon", "annotation_collision"})

    def test_distinct_single_cavity_group_heights_are_valid(self):
        pads = [{"center_um": [0, 0], "size_um": [90, 90]},
                {"center_um": [150, 0], "size_um": [90, 90]}]
        accepted = {"synthetic": {"device_kind": "single", "source": "synthetic-test-only", "local_pads": pads}}
        groups = [{"component_profile": "synthetic", "anchor_um": [0, 100], "local_pads": copy.deepcopy(pads)},
                  {"component_profile": "synthetic", "anchor_um": [0, 900], "local_pads": copy.deepcopy(pads)}]
        self.assertEqual(validate_pad_groups("single", groups, accepted), [])
        groups[1]["local_pads"][1]["center_um"][0] = 151
        self.assertIn("pad_group_changed", self.codes(validate_pad_groups("single", groups, accepted)))
        self.assertIn("pad_device_kind", self.codes(validate_pad_groups("array", groups, accepted)))

    def test_unresolved_process_values_stay_unresolved(self):
        profile = load_profile()
        self.assertTrue(all(value is None for value in profile["unresolved_process_values"].values()))
        self.assertIsNone(profile["pads"]["group_local_geometry"])
        self.assertFalse(profile["pads"]["all_groups_same_height"])

    def test_missing_or_invalid_pad_geometry_and_anchor_cannot_pass(self):
        source = {"approved": {"source": "synthetic accepted component", "device_kind": "single"}}
        group = {"component_profile": "approved", "anchor_um": [0, 100]}
        self.assertEqual(self.codes(validate_pad_groups("single", [group], source)),
                         {"pad_component_geometry_invalid", "pad_group_geometry_invalid"})
        for pads in ([], [{"center_um": [float("nan"), 0], "size_um": [90, 90]}],
                     [{"center_um": [0, 0], "size_um": [0, 90]}],
                     [{"center_um": [0, 0], "size_um": [90, float("inf")]}]):
            with self.subTest(pads=pads):
                source["approved"]["local_pads"] = pads
                group["local_pads"] = copy.deepcopy(pads)
                self.assertIn("pad_component_geometry_invalid", self.codes(validate_pad_groups("single", [group], source)))
                self.assertIn("pad_group_geometry_invalid", self.codes(validate_pad_groups("single", [group], source)))
        valid = [{"center_um": [0, 0], "size_um": [90, 90]}]
        source["approved"]["local_pads"] = valid
        group["local_pads"] = copy.deepcopy(valid)
        for anchor in ([float("nan"), 0], [0, float("inf")], [True, 0]):
            group["anchor_um"] = anchor
            self.assertEqual(self.codes(validate_pad_groups("single", [group], source)), {"pad_anchor_missing"})


if __name__ == "__main__":
    unittest.main()
