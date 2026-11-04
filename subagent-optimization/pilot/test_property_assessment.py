"""Synthetic CSV contract tests; fixtures are not live scientific evidence."""
from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest

from rdkit import rdBase

from pilot.property_assessment import KIND, PlatformPropertyAssessor, _qualified


REFERENCE = {"id": "test-original-unspecified", "form_id": "test-unspecified-stereo",
             "representation": "N1(C(CN2CCN(CC2)CC3=CC=C(C=C3)OC)=O)C(CC4=C1C=CC=C4)C",
             "source": "public original reference structure; TEST FIXTURE"}


def configuration():
    return {"kind": KIND, "reference": deepcopy(REFERENCE), "rdkit_version": rdBase.rdkitVersion,
            "property_column": "Lipophilicity", "target_min": 0, "target_max": 3,
            "baseline": {"lipophilicity": -8.72, "qed": 0.800452829768805, "lead_similarity": 1.0},
            "baseline_evidence_sha256": "TEST_ONLY_NOT_A_LIVE_RECEIPT"}


class PropertyAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assessor = PlatformPropertyAssessor(configuration())

    def csv(self, name, rows):
        path = self.root / name
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["SMILES", "Lipophilicity", "QED", "source-note"])
            writer.writerows((smiles, score, "rounded-provider-value-is-not-used", "TEST_FIXTURE")
                             for smiles, score in rows)
        return path

    def test_inclusive_property_strict_secondary_same_candidate_rules(self):
        baseline = configuration()["baseline"]
        for score in (0, 3, 1.234567890123456):
            self.assertTrue(_qualified({"lipophilicity": score, "qed": 0.9, "lead_similarity": .700001}, baseline))
        for score in (-0.00001, 3.00001, None, float("nan")):
            self.assertFalse(_qualified({"lipophilicity": score, "qed": .9, "lead_similarity": .8}, baseline))
        self.assertFalse(_qualified({"lipophilicity": 1, "qed": baseline["qed"], "lead_similarity": .8}, baseline))
        self.assertFalse(_qualified({"lipophilicity": 1, "qed": .9, "lead_similarity": .7}, baseline))
        self.assertFalse(_qualified({"lipophilicity": 4, "qed": .9, "lead_similarity": .8}, baseline))
        self.assertFalse(_qualified({"lipophilicity": 1, "qed": .7, "lead_similarity": .8}, baseline))

    def test_reference_duplicate_raw_scores_extra_columns_and_invalid_rows(self):
        baseline = self.assessor.baseline_check()
        self.assertEqual(baseline["baseline_model_evaluations"], 0)
        self.assertEqual(baseline["summaries"][0]["values"]["lipophilicity"], -8.72)
        first = self.assessor.assess_csv(self.csv("first.csv", [
            (REFERENCE["representation"], -8.72), ("CCO", -1.23456789012345),
            ("OCC", -1.23456789012345), ("CCN", 2.55), ("INVALID", 7),
            ("CC.CC", 1), ("CC |unknown|", 1), ("CCC", "NaN")]))
        self.assertEqual(first["raw_rows"], 8)
        self.assertEqual(first["duplicate_rows"], 2)
        self.assertEqual(first["invalid_rows"], 2)
        self.assertEqual(first["unresolved_rows"], 2)
        self.assertEqual(first["new_unique_candidate_evaluations"], 2)
        self.assertEqual(first["reported_property_prediction_rows"], 7)
        self.assertIsNone(first["total_model_row_evaluations"])
        self.assertEqual(first["rows"][1]["assessment"]["values"]["lipophilicity"], -1.23456789012345)
        self.assertEqual(first["rows"][3]["assessment"]["values"]["lipophilicity"], 2.55)
        self.assertTrue(all(row["source_columns"]["source-note"] == "TEST_FIXTURE" for row in first["rows"]))
        self.assertNotIn(REFERENCE["id"], first["qualified_candidate_ids"])
        original_cache = deepcopy(first["cache"])
        second = self.assessor.assess_csv(self.csv("second.csv", [("OCC", -1.23456789012345)]), first["cache"])
        self.assertEqual(second["new_unique_candidate_evaluations"], 0)
        self.assertEqual(second["rows"][0]["candidate_id"], first["rows"][1]["candidate_id"])
        self.assertEqual(original_cache, first["cache"])

    def test_conflicting_duplicates_never_choose_first_or_last_and_replay_is_idempotent(self):
        path = self.csv("conflicts.csv", [("CCO", 1), ("OCC", 2)])
        first = self.assessor.assess_csv(path)
        self.assertTrue(all(row["status"] == "unresolved" for row in first["rows"]))
        self.assertIsNone(first["cache"]["CCO"]["summary"]["values"]["lipophilicity"])
        self.assertEqual(first["qualified_candidate_ids"], [])
        replay = self.assessor.assess_csv(path, first["cache"])
        self.assertEqual(replay["cache"], first["cache"])
        prior = self.assessor.assess_csv(self.csv("prior.csv", [("CCN", 0)]))
        later = self.assessor.assess_csv(self.csv("later.csv", [("NCC", 3)]), prior["cache"])
        self.assertTrue(later["rows"][0]["assessment"]["property_prediction_conflict"])
        ref = self.assessor.assess_csv(self.csv("ref-conflict.csv", [(REFERENCE["representation"], 1)]))
        self.assertTrue(ref["reference_score_conflict"])
        self.assertEqual(ref["evaluation_blockers"], ["original_reference_property_conflict"])
        self.assertEqual(ref["qualified_candidate_ids"], [])

    def test_exact_stereo_and_cache_provenance_are_bound(self):
        first = self.assessor.assess_csv(self.csv("stereo.csv", [
            ("C[C@H](F)Cl", 1), ("C[C@@H](F)Cl", 1), ("CC(F)Cl", 1)]))
        self.assertEqual(len({r["candidate_id"] for r in first["rows"]}), 3)
        self.assertEqual(first["new_unique_candidate_evaluations"], 3)
        bad = deepcopy(first["cache"])
        next(e for g, e in bad.items() if g != self.assessor.lead_graph)["property_evidence"][0]["reported_text"] = "2"
        with self.assertRaises(ValueError): self.assessor.assess_csv(self.csv("replay.csv", [("CCO", 1)]), bad)
        changed = configuration(); changed["arm_scope"] = "another-arm"
        with self.assertRaises(ValueError): PlatformPropertyAssessor(changed).assess_csv(self.csv("other.csv", [("CCO", 1)]), first["cache"])
        changed = configuration(); changed["rdkit_version"] = "different"
        with self.assertRaises(ValueError): PlatformPropertyAssessor(changed)

    def test_bad_csv_and_wrong_reference_baseline_fail_clearly(self):
        for text in ("SMILES\nCCO\n", "SMILES,Lipophilicity,Lipophilicity\nCCO,1,2\n",
                     "SMILES,Lipophilicity\nCCO\n"):
            path = self.root / "bad.csv"; path.write_text(text)
            with self.assertRaises(ValueError): self.assessor.assess_csv(path)
        changed = configuration(); changed["baseline"]["qed"] = .8
        with self.assertRaises(ValueError): PlatformPropertyAssessor(changed)


if __name__ == "__main__":
    unittest.main()
