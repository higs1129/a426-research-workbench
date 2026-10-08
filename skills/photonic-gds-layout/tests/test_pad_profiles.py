"""Regression against installed-source profiles, not duplicated test profiles."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from process_rules import load_profile, validate_pad_groups


class PadProfileTests(unittest.TestCase):
    def setUp(self):
        self.pads = load_profile()["pads"]
        self.components = self.pads["accepted_local_profiles"]

    def group(self, name, anchor):
        return {"component_profile": name, "anchor_um": anchor,
                "local_pads": copy.deepcopy(self.components[name]["local_pads"])}

    @staticmethod
    def codes(findings):
        return {finding.code for finding in findings}

    def test_chip7_and_chip9_are_single_components_at_independent_heights(self):
        for name in ("single-ring-heater-stagger150", "single-membrane-phase-stagger200"):
            with self.subTest(profile=name):
                groups = [self.group(name, [200, 400]), self.group(name, [900, 1700])]
                self.assertEqual(self.components[name]["device_kind"], "single")
                self.assertEqual(validate_pad_groups("single", groups, self.components), [])
                self.assertIn("pad_device_kind", self.codes(validate_pad_groups("array", groups, self.components)))

    def test_true_shared_optical_bus_array_accepts_array_rejects_single(self):
        name = "array-shared-bus-ring-heater-stagger200"
        groups = [self.group(name, [900, 3900]), self.group(name, [1150, 3900])]
        self.assertEqual(validate_pad_groups("array", groups, self.components), [])
        self.assertIn("pad_device_kind", self.codes(validate_pad_groups("single", groups, self.components)))
        self.assertEqual(self.components[name]["local_pads"][1]["center_um"], [100, 200])

    def test_same_pair_geometry_does_not_make_single_and_array_interchangeable(self):
        single = "single-membrane-phase-stagger200"
        array = "array-shared-bus-ring-heater-stagger200"
        self.assertEqual(self.components[single]["local_pads"], self.components[array]["local_pads"])
        mixed = [self.group(single, [200, 700]), self.group(array, [500, 3900])]
        for device_kind in ("single", "array"):
            self.assertIn("pad_device_kind", self.codes(validate_pad_groups(device_kind, mixed, self.components)))

    def test_fixed_pair_spacing_change_is_rejected_in_actual_single_profile(self):
        group = self.group("single-ring-heater-stagger150", [200, 400])
        group["local_pads"][1]["center_um"][1] = 200
        self.assertIn("pad_group_changed", self.codes(validate_pad_groups("single", [group], self.components)))

    def test_retired_misclassified_ids_cannot_silently_select_array(self):
        for retired in ("array-ring-heater-stagger150", "array-membrane-phase-stagger200"):
            self.assertNotIn(retired, self.components)
            group = self.group("single-membrane-phase-stagger200", [200, 400])
            group["component_profile"] = retired
            self.assertIn("pad_source_missing", self.codes(validate_pad_groups("array", [group], self.components)))

    def test_no_global_group_height_or_electrical_connection_is_inferred(self):
        self.assertIsNone(self.pads["group_anchors"])
        self.assertIsNone(self.pads["electrical_topology"])
        self.assertFalse(self.pads["all_groups_same_height"])
        for component in self.components.values():
            self.assertTrue(component["source"])
            self.assertTrue(component["optical_topology"])
            self.assertTrue(component["source_electrical_topology"])
            self.assertNotIn("group_anchors", component)


if __name__ == "__main__":
    unittest.main()
