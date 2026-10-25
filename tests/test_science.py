"""Offline evidence checks: no MATLAB process and no model API requests."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import science


def fixture():
    # Small arrays test scientific data conventions independently of the
    # production Plan's 51-point minimum. Numbers are synthetic test data.
    plan = {"template": "munk_5000m", "frequency_hz": 50, "source_depth_m": 1000,
            "frequencies_hz": [50], "source_depths_m": [1000],
            "receiver_depth_m": 2501, "range_min_km": 1, "range_max_km": 3,
            "range_points": 3, "depth_points": 3}
    result = {"ranges_m": [1000, 2000, 3000], "depths_m": [0, 2500, 5000],
              "tl_db": [[None, None, None], [80, 65, 70], [90, 82, 78]],
              "curve_tl_db": [80, 65, 70], "shape": [3, 3], "valid_ratio": 2 / 3,
              "frequency_hz": 50, "source_depth_m": 1000,
              "requested_receiver_depth_m": 2501, "actual_receiver_depth_m": 2500,
              "receiver_depth_error_m": 1, "reference": "AT FIELD normalized pressure; coherent modal field",
              "matlab_version": "synthetic-test-version"}
    return plan, result


class ScienceChecks(unittest.TestCase):
    def setUp(self):
        self.plan, self.result = fixture()

    def assert_failed(self, key, result=None, plan=None):
        report = science.verify_result(result or self.result, plan or self.plan)
        self.assertFalse(report["ok"])
        check = next(item for item in report["checks"] if item["id"] == key)
        self.assertFalse(check["passed"], report)
        return report

    def test_valid_masked_field_and_nonmonotonic_curve_are_accepted(self):
        report = science.validate_result(self.result, self.plan)
        self.assertTrue(report["ok"])
        self.assertEqual(report["metrics"]["finite_samples"], 6)
        self.assertEqual(report["metrics"]["total_samples"], 9)
        self.assertAlmostEqual(report["metrics"]["valid_ratio"], 2 / 3)
        self.assertGreater(self.result["curve_tl_db"][0], self.result["curve_tl_db"][1])
        self.assertLess(self.result["curve_tl_db"][1], self.result["curve_tl_db"][2])

    def test_unknown_template_does_not_silently_use_munk(self):
        self.plan["template"] = "shallow_real_sea"
        self.assert_failed("template")

    def test_axis_sorting_and_uniform_sampling_are_independent_checks(self):
        self.result["ranges_m"] = [1000, 2100, 3000]
        report = self.assert_failed("range_grid")
        self.assertTrue(next(c for c in report["checks"] if c["id"] == "range_axis")["passed"])
        self.result["ranges_m"] = [3000, 2000, 1000]
        self.assert_failed("range_axis")

    def test_axis_range_or_length_mismatch_is_rejected(self):
        self.result["depths_m"] = [0, 2500, 5100]
        self.assert_failed("depth_grid")
        self.plan["range_points"] = 4
        self.assert_failed("range_grid")

    def test_nonfinite_axes_and_non_numeric_samples_fail_without_crashing(self):
        self.result["ranges_m"][1] = float("nan")
        self.assert_failed("range_axis")
        self.result["ranges_m"][1] = 10 ** 1000
        self.assert_failed("range_axis")
        self.plan, self.result = fixture()
        self.result["tl_db"][1][0] = "80 dB"
        self.assert_failed("sample_types")
        self.plan, self.result = fixture()
        self.result["tl_db"][1][0] = True
        self.assert_failed("sample_types")

    def test_transposed_nonsquare_output_fails_dimensions(self):
        self.plan["range_points"] = 4
        self.plan["range_max_km"] = 4
        self.result["ranges_m"] = [1000, 2000, 3000, 4000]
        self.result["tl_db"] = [[None, 80, 90], [None, 65, 82], [None, 70, 78], [None, 71, 79]]
        self.result["shape"] = [4, 3]
        self.result["curve_tl_db"] = [80, 65, 70, 71]
        self.assert_failed("matrix_shape")

    def test_declared_shape_and_sample_ratio_are_checked_against_data(self):
        self.result["shape"] = [1, 9]
        self.assert_failed("declared_shape")
        self.result["valid_ratio"] = 1
        self.assert_failed("valid_ratio")

    def test_frequency_and_source_depth_must_match_single_case(self):
        self.result["frequency_hz"] = 100
        self.assert_failed("frequency")
        self.result["source_depth_m"] = 500
        self.assert_failed("source_depth")
        self.plan.pop("frequency_hz")
        self.plan["frequencies_hz"] = [50, 100]
        self.assert_failed("frequency")

    def test_receiver_request_error_and_nearest_row_are_independent(self):
        self.result["actual_receiver_depth_m"] = 5000
        self.result["receiver_depth_error_m"] = 2499
        self.assert_failed("receiver_nearest")
        self.plan, self.result = fixture()
        self.result["requested_receiver_depth_m"] = 2500
        self.assert_failed("receiver_request")
        self.result["receiver_depth_error_m"] = 0
        self.assert_failed("receiver_error")

    def test_curve_cannot_be_detached_from_reported_depth(self):
        self.result["curve_tl_db"][0] = 81
        self.assert_failed("curve_row")
        self.result["curve_tl_db"] = [80, 65]
        self.assert_failed("curve_length")

    def test_all_invalid_field_cannot_pass(self):
        self.result["tl_db"] = [[None] * 3 for _ in range(3)]
        self.result["curve_tl_db"] = [None] * 3
        self.result["valid_ratio"] = 0
        self.assert_failed("finite_samples")

    def test_grid_coordinates_allow_documented_float_precision(self):
        self.result["ranges_m"][1] += 0.002
        self.result["depths_m"][1] += 0.001
        self.assertTrue(science.verify_result(self.result, self.plan)["ok"])

    def test_analysis_uses_actual_values_and_never_ranks_seas(self):
        analysis = science.analyze_result(self.result, self.plan)
        self.assertEqual(analysis["field"]["tl_median_db"], 79)
        self.assertEqual(analysis["curve"]["tl_min_db"], 65)
        self.assertEqual(analysis["curve"]["min_tl_range_km"], 2)
        self.assertFalse(analysis["comparability"]["can_rank_environments"])
        self.assertTrue(any("收敛" in note for note in analysis["limits"]))
        self.assertTrue(any("相干" in note for note in analysis["limits"]))
        json.dumps(analysis, allow_nan=False)

    def test_invalid_analysis_raises_with_named_evidence(self):
        self.result["frequency_hz"] = 90
        with self.assertRaises(science.ResultValidationError) as caught:
            science.analyze_result(self.result, self.plan)
        self.assertFalse(caught.exception.report["ok"])
        self.assertIn("实际频率", str(caught.exception))

    def test_empty_receiver_curve_has_no_invented_extreme(self):
        self.plan["receiver_depth_m"] = 1
        self.result.update(requested_receiver_depth_m=1, actual_receiver_depth_m=0,
                           receiver_depth_error_m=1, curve_tl_db=[None] * 3)
        analysis = science.analyze_result(self.result, self.plan)
        self.assertEqual(analysis["curve"], {"finite_samples": 0})
        self.assertNotIn("curve_min", [h["id"] for h in analysis["highlights"]])

    def test_comparison_permits_declared_frequency_control_not_ranking(self):
        other_plan = copy.deepcopy(self.plan)
        other_plan["frequency_hz"] = 100
        other_result = copy.deepcopy(self.result)
        other_result["frequency_hz"] = 100
        other_result["tl_db"] = [[v - 3 if v is not None else None for v in row] for row in self.result["tl_db"]]
        other_result["curve_tl_db"] = [v - 3 for v in self.result["curve_tl_db"]]
        comparison = science.compare_results(self.result, other_result, self.plan, other_plan)
        self.assertTrue(comparison["comparable"])
        self.assertEqual(comparison["changed_controlled_variables"], ["frequency_hz"])
        self.assertEqual(comparison["deltas"]["field_median_tl_db_b_minus_a"], -3)
        self.assertFalse(comparison["can_rank_environments"])

    def test_different_grids_cannot_be_ranked_by_field_median(self):
        other_plan = copy.deepcopy(self.plan)
        other_plan.update(range_points=4, range_max_km=4)
        other_result = copy.deepcopy(self.result)
        other_result["ranges_m"].append(4000)
        for row in other_result["tl_db"]:
            row.append(row[-1])
        other_result["curve_tl_db"].append(70)
        other_result["shape"] = [3, 4]
        comparison = science.compare_results(self.result, other_result, self.plan, other_plan)
        self.assertFalse(comparison["comparable"])
        self.assertFalse(comparison["checks"]["same_ranges_m"])
        self.assertIsNone(comparison["deltas"])

    def test_different_valid_sample_population_blocks_median_comparison(self):
        other = copy.deepcopy(self.result)
        other["tl_db"][2][2] = None
        other["valid_ratio"] = 5 / 9
        comparison = science.compare_results(self.result, other, self.plan, self.plan)
        self.assertTrue(comparison["checks"]["both_results_verified"])
        self.assertFalse(comparison["checks"]["same_finite_mask"])
        self.assertFalse(comparison["comparable"])

    def test_manifest_records_actual_hashes_without_private_configuration(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "result.json").write_text(json.dumps(self.result), encoding="utf-8")
            for file_name in ["case.json", "case.env", "case.flp", "run_ocean_case.m", "curve.csv"]:
                (folder / file_name).write_text("synthetic test artifact\n", encoding="utf-8")
            plan = {**self.plan, "toolbox_path": "private-toolbox-path", "api_key": "never-publish-this-key"}
            manifest = science.write_manifest("test-case-01", plan, folder,
                                              started_at="2026-10-13T08:00:00+00:00",
                                              solver_versions={"kraken": "reported-kraken-version"})
            text = (folder / "manifest.json").read_text(encoding="utf-8")
            self.assertNotIn("never-publish", text)
            self.assertNotIn("private-toolbox", text)
            self.assertNotIn(str(folder), text)
            self.assertEqual(manifest["solver"]["kraken_version"], "reported-kraken-version")
            self.assertIsNone(manifest["solver"]["field_version"])
            self.assertEqual(manifest["solver"]["matlab_version"], "synthetic-test-version")
            self.assertEqual(manifest["measured"]["frequency_hz"], 50)
            result_entry = next(a for a in manifest["artifacts"] if a["name"] == "result.json")
            self.assertEqual(result_entry["sha256"], hashlib.sha256((folder / "result.json").read_bytes()).hexdigest())
            self.assertEqual(manifest["missing_artifacts"], [])

    def test_manifest_does_not_trust_supplied_success_claim(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            self.result["frequency_hz"] = 99
            (folder / "result.json").write_text(json.dumps(self.result), encoding="utf-8")
            with self.assertRaises(science.ResultValidationError):
                science.build_manifest("test", self.plan, folder, validation={"ok": True})

    def test_missing_manifest_artifacts_remain_explicit(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "result.json").write_text(json.dumps(self.result), encoding="utf-8")
            manifest = science.build_manifest("test", self.plan, folder)
            self.assertIn("case.env", manifest["missing_artifacts"])
            self.assertIn("run_ocean_case.m", manifest["missing_artifacts"])
            self.assertEqual([a["name"] for a in manifest["artifacts"]], ["result.json"])


class CourseExercises(unittest.TestCase):
    def test_presets_document_limits_and_do_not_fabricate_tl_results(self):
        data = json.loads((ROOT / "backend/data/exercises.json").read_text(encoding="utf-8"))
        exercises = data["exercises"]
        self.assertGreaterEqual(len(exercises), 8)
        self.assertEqual(len({e["id"] for e in exercises}), len(exercises))
        graph = json.loads((ROOT / "backend/data/course_graph.json").read_text(encoding="utf-8"))
        nodes = {n["id"] for n in graph["nodes"]}
        for exercise in exercises:
            self.assertTrue(exercise["input_ranges"])
            self.assertTrue(exercise["expected_outputs"])
            self.assertTrue(exercise["scientific_notes"])
            self.assertTrue(set(exercise["knowledge_nodes"]) <= nodes)
            if exercise["runnable"]:
                plan = exercise["plan"]
                self.assertEqual(plan["template"], "munk_5000m")
                self.assertLessEqual(len(plan["frequencies_hz"]) * len(plan["source_depths_m"]), 4)
                self.assertTrue(all(10 <= f <= 200 for f in plan["frequencies_hz"]))
                self.assertTrue(all(0 < z < 5000 for z in plan["source_depths_m"]))
                self.assertNotIn("tl_db", exercise)
            else:
                self.assertIsNone(exercise["plan"])


if __name__ == "__main__":
    unittest.main()
