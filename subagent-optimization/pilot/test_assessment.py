"""Actual pinned-assessor smoke and intake invariants; no generation or remote jobs."""
from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest

from pilot.assessment import PinnedAssessor, SCORER_SHA256, MODEL_SHA256, LEAD_SHA256, _qualified, digest


TASK = Path("/home/boltzmann13/science-environments/environments/small-molecule-lead-optimization/tasks/drd2")
MODEL = Path("/home/boltzmann13/.cache/science-environments/drd2/a0622fc2fe16812c7530bca20dcca9a9fd874513/support/drd2.pkl")


def configuration():
    return {"scorer_path": str(TASK / "score.py"), "model_path": str(MODEL),
            "lead_path": str(TASK / "lead.json"), "scorer_sha256": SCORER_SHA256,
            "model_sha256": MODEL_SHA256, "lead_sha256": LEAD_SHA256,
            "method_version": "drd2-task-assessment-v1;rdkit=2025.09.4;numpy=2.2.4",
            "baseline": {"drd2_p_active": 0.7190727026540751,
                         "qed": 0.800452829768805, "lead_similarity": 1.0}}


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assessor = PinnedAssessor(configuration())

    def csv(self, name, values):
        path = self.root / name
        with path.open("w", newline="") as f:
            writer = csv.writer(f); writer.writerow(["SMILES", "origin"])
            writer.writerows((value, "TEST_INPUT_NOT_A_GENERATOR_RESULT") for value in values)
        return path

    def test_real_baseline_and_duplicate_cache_preserve_every_returned_row(self):
        baseline = self.assessor.baseline_check()
        self.assertEqual(baseline["summaries"][0]["values"]["drd2_p_active"], configuration()["baseline"]["drd2_p_active"])
        self.assertFalse(baseline["summaries"][0]["qualified_improvement"])
        first = self.assessor.assess_csv(self.csv("first.csv", [self.assessor.lead["representation"], "CCO", "OCC", "NOT_A_MOLECULE", "CC.CC", "CC |unknown|"]))
        self.assertEqual(first["raw_rows"], 6)
        self.assertEqual(first["new_unique_candidate_evaluations"], 1)
        self.assertEqual(first["duplicate_rows"], 2)
        self.assertEqual(first["invalid_rows"], 2)
        self.assertEqual(first["unresolved_rows"], 1)
        self.assertEqual(first["baseline_model_evaluations"], 1)
        self.assertEqual(first["assessment"]["scored_records"], first["new_unique_candidate_evaluations"] + 1)
        self.assertTrue(all(row["edit_attribution"] == "unknown" for row in first["rows"]))
        old_cache = deepcopy(first["cache"])
        second = self.assessor.assess_csv(self.csv("second.csv", ["OCC", "CCN"]), first["cache"])
        self.assertEqual(second["new_unique_candidate_evaluations"], 1)
        self.assertEqual(second["duplicate_rows"], 1)
        self.assertEqual(second["rows"][0]["candidate_id"], first["rows"][1]["candidate_id"])
        self.assertEqual(first["cache"], old_cache)
        self.assertEqual(second["rows"][0]["assessment"]["values"], first["rows"][1]["assessment"]["values"])

    def test_assigned_and_unspecified_stereochemistry_are_distinct_supplied_forms(self):
        values = ["C[C@H](F)Cl", "C[C@@H](F)Cl", "CC(F)Cl", "C[C@H](F)Cl"]
        result = self.assessor.assess_csv(self.csv("stereo.csv", values))
        self.assertEqual(result["new_unique_candidate_evaluations"], 3)
        self.assertEqual(result["duplicate_rows"], 1)
        self.assertEqual(len({r["candidate_id"] for r in result["rows"]}), 3)
        self.assertEqual([r["representation"] for r in result["rows"]], values)

    def test_bad_csv_schema_and_trailing_tokens_do_not_silently_pass(self):
        for text in ("smiles\nCCO\n", "SMILES,SMILES\nCCO,CCN\n", "SMILES,origin\nCCO\n"):
            path = self.root / "bad.csv"; path.write_text(text)
            with self.assertRaises(ValueError): self.assessor.assess_csv(path)
        result = self.assessor.assess_csv(self.csv("names.csv", ["CCO named_molecule"]))
        self.assertEqual(result["invalid_rows"], 1)
        self.assertEqual(result["new_unique_candidate_evaluations"], 0)

    def test_wrong_pins_stale_method_and_corrupted_cache_are_rejected(self):
        wrong = configuration(); wrong["model_sha256"] = "0" * 64
        with self.assertRaises(ValueError): PinnedAssessor(wrong)
        wrong = configuration(); wrong["method_version"] = "different-assessor"
        with self.assertRaises(ValueError): PinnedAssessor(wrong)
        first = self.assessor.assess_csv(self.csv("cached.csv", ["CCO"]))
        corrupted = deepcopy(first["cache"])
        corrupted["CCO"]["summary"]["values"]["qed"] = 1.0
        with self.assertRaises(ValueError): self.assessor.assess_csv(self.csv("replay.csv", ["CCO"]), corrupted)
        conflicting = deepcopy(first["cache"])
        conflicting["CCO"]["observations"][0]["value"] = 0.12345
        conflicting["CCO"]["entry_sha256"] = digest({k: v for k, v in conflicting["CCO"].items() if k != "entry_sha256"})
        with self.assertRaises(ValueError): self.assessor.assess_csv(self.csv("conflicting.csv", ["CCO"]), conflicting)

    def test_success_requires_one_candidate_above_both_baselines_and_strict_similarity(self):
        baseline = configuration()["baseline"]
        self.assertFalse(_qualified(dict(baseline), baseline))
        self.assertFalse(_qualified({**baseline, "drd2_p_active": 0.9}, baseline))
        self.assertFalse(_qualified({**baseline, "qed": 0.9}, baseline))
        self.assertFalse(_qualified({"drd2_p_active": 0.9, "qed": 0.9, "lead_similarity": 0.7}, baseline))
        self.assertTrue(_qualified({"drd2_p_active": 0.9, "qed": 0.9, "lead_similarity": 0.700001}, baseline))


if __name__ == "__main__":
    unittest.main()
