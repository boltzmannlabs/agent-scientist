"""Unit tests: selection record validator."""
import sys

sys.dont_write_bytecode = True  # imported by CI runners; never leave bytecode in the package tree
import json
import subprocess
import sys
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]
SR = P / "scripts/selection_record.py"


def valid_record():
    return {
        "record_version": 1,
        "basis": {"candidate_source": "run/ranked.csv", "criteria": {"weights": {"efficacy": 0.4}}, "n_candidates": 2},
        "ranked": [
            {"rank": 1, "id": "a", "properties": {"efficacy": 0.8}},
            {"rank": 2, "id": "b", "properties": {"efficacy": 0.7}},
        ],
        "best_computational_candidate": {"id": "a", "property_attribution": ["efficacy +0.10 vs runner-up"]},
        "limitations": ["NOT experimental validation; best_design remains null"],
    }


class SelectionRecord(unittest.TestCase):
    def run_v(self, path):
        return subprocess.run([sys.executable, "-B", str(SR), "validate", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_valid_passes(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(valid_record(), f); p = f.name
        r = self.run_v(p); os.unlink(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(r.stdout)["status"], "PASS")

    def test_rank1_mismatch_fails(self):
        import tempfile
        import os
        rec = valid_record(); rec["best_computational_candidate"]["id"] = "b"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(rec, f); p = f.name
        r = self.run_v(p); os.unlink(p)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(any("rank-1" in x for x in json.loads(r.stdout)["problems"]))

    def test_missing_not_experimental_limitation_fails(self):
        import tempfile
        import os
        rec = valid_record(); rec["limitations"] = ["some other note"]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(rec, f); p = f.name
        r = self.run_v(p); os.unlink(p)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(any("NOT experimental" in x or "experimental" in x for x in json.loads(r.stdout)["problems"]))


if __name__ == "__main__":
    unittest.main()
