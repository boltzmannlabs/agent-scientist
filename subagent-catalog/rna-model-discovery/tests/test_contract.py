"""Unit tests: preflight routing, spec validation, registry state machine (stdlib only)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / "scripts"))
import request_contract as rc  # noqa: E402
import validate_spec as vs  # noqa: E402


class Routing(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(rc.preflight({"mode": "SETUP"})["status"], "SETUP_FIRST")
        self.assertEqual(rc.preflight({"mode": "AUDIT"})["status"], "AUDIT_ONLY")
        self.assertEqual(rc.preflight({"mode": "fish"})["status"], "INVALID_REQUEST")
        self.assertEqual(rc.preflight([1])["status"], "INVALID_REQUEST")

    def test_discover_requires_authorization(self):
        out = rc.preflight({"mode": "DISCOVER", "task_description": "t", "capability_gap": "g", "output_root": "o"})
        self.assertEqual(out["status"], "NEEDS_INPUT")
        self.assertIn("search_authorization", out["missing_inputs"])

    def test_discover_complete(self):
        out = rc.preflight({"mode": "DISCOVER", "task_description": "t", "capability_gap": "g",
                            "output_root": "o", "search_authorization": "yes"})
        self.assertEqual(out["status"], "METADATA_COMPLETE_REQUIRES_PARENT_AND_CONNECTOR_CHECKS")
        self.assertFalse(out["network_used"])

    def test_evaluate_and_spec_gaps(self):
        self.assertIn("candidate_manifest", rc.preflight(
            {"mode": "EVALUATE", "task_description": "t", "output_root": "o"})["missing_inputs"])
        self.assertIn("evidence_manifest", rc.preflight(
            {"mode": "SPEC", "task_description": "t", "output_root": "o", "selected_candidate": "m"})["missing_inputs"])


class SpecValidation(unittest.TestCase):
    def test_synthetic_passes(self):
        spec = json.loads((P / "tests/synthetic_spec.json").read_text())
        self.assertEqual(vs.structural(spec), [])

    def test_invalid_fails(self):
        spec = json.loads((P / "tests/invalid_spec.json").read_text())
        self.assertNotEqual(vs.structural(spec), [])

    def test_no_weights_cannot_carry_checkpoints(self):
        spec = json.loads((P / "tests/synthetic_spec.json").read_text())
        spec["weights_availability"] = "NO_WEIGHTS"
        self.assertTrue(any("NO_WEIGHTS" in p for p in vs.structural(spec)))


class Registry(unittest.TestCase):
    """Exercises the shared registry CLI end-to-end in a temp directory."""

    def run_reg(self, *args):
        return subprocess.run([sys.executable, "-B", str(P / "scripts/registry.py"), *args],
                              capture_output=True, text=True)

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = str(Path(self.tmp.name) / "reg.json")
        r = self.run_reg("init", self.reg)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ladder_adjacent_only(self):
        r = self.run_reg("add", self.reg, "--id", "m1", "--domain", "mrna", "--task", "te-prediction",
                         "--repo", "example.invalid/m1")
        self.assertEqual(r.returncode, 0, r.stdout)
        r = self.run_reg("transition", self.reg, "m1", "INSTALLED")
        self.assertEqual(r.returncode, 2)  # skipping refused
        for st in ("EVIDENCE_REVIEWED", "WEIGHTS_AVAILABLE"):
            r = self.run_reg("transition", self.reg, "m1", st, "--evidence", "fixture")
            self.assertEqual(r.returncode, 0, r.stdout)
        r = self.run_reg("transition", self.reg, "m1", "DISCOVERED")
        self.assertEqual(r.returncode, 2)  # backward refused
        r = self.run_reg("show", self.reg, "m1")
        self.assertIn("WEIGHTS_AVAILABLE", r.stdout)

    def test_discovery_side_cannot_install(self):
        r = self.run_reg("add", self.reg, "--id", "m2", "--domain", "sirna", "--task", "x",
                         "--repo", "x.invalid", "--state", "INSTALLED")
        self.assertEqual(r.returncode, 2)  # reader states only
        r = self.run_reg("validate", self.reg)
        self.assertEqual(r.returncode, 0)

    def test_no_silent_overwrite(self):
        self.run_reg("add", self.reg, "--id", "m3", "--domain", "grna", "--task", "x", "--repo", "x.invalid")
        r = self.run_reg("add", self.reg, "--id", "m3", "--domain", "grna", "--task", "x", "--repo", "x.invalid")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
