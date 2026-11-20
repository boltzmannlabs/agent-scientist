"""Unit tests: execution preflight, report validation, execution-side registry transitions (stdlib only)."""
import sys

sys.dont_write_bytecode = True  # imported by CI runners; never leave bytecode in the package tree
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / "scripts"))
import request_contract as rc  # noqa: E402
import validate_report as vr  # noqa: E402


class Routing(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(rc.preflight({"mode": "SETUP"})["status"], "SETUP_FIRST")
        self.assertEqual(rc.preflight({"mode": "AUDIT"})["status"], "AUDIT_ONLY")
        self.assertEqual(rc.preflight({"mode": "deploy"})["status"], "INVALID_REQUEST")
        self.assertEqual(rc.preflight("nope")["status"], "INVALID_REQUEST")

    def test_install_requires_egress(self):
        out = rc.preflight({"mode": "INSTALL", "model_integration_spec": "s.json",
                            "approved_destination": "envs/x", "output_root": "o"})
        self.assertEqual(out["status"], "NEEDS_INPUT")
        self.assertIn("egress_authorization", out["missing_inputs"])
        self.assertFalse(out["installation_executed"])

    def test_install_complete(self):
        out = rc.preflight({"mode": "INSTALL", "model_integration_spec": "s.json",
                            "approved_destination": "envs/x", "egress_authorization": "ok", "output_root": "o"})
        self.assertEqual(out["status"], "METADATA_COMPLETE_REQUIRES_PARENT_AND_NATIVE_CHECKS")

    def test_run_and_register_gaps(self):
        self.assertIn("environment_receipt", rc.preflight(
            {"mode": "RUN", "model_integration_spec": "s.json", "output_root": "o"})["missing_inputs"])
        self.assertIn("execution_report", rc.preflight(
            {"mode": "REGISTER", "registry_path": "r.json", "entry_id": "m", "target_state": "INSTALLED"})["missing_inputs"])


class ReportValidation(unittest.TestCase):
    def test_synthetic_passes(self):
        rep = json.loads((P / "tests/synthetic_report.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(vr.structural(rep), [])

    def test_invalid_fails(self):
        rep = json.loads((P / "tests/invalid_report.json").read_text(encoding="utf-8-sig"))
        self.assertNotEqual(vr.structural(rep), [])

    def test_completed_requires_records(self):
        rep = json.loads((P / "tests/synthetic_report.json").read_text(encoding="utf-8-sig"))
        rep["inference_status"]["status"] = "COMPLETED"
        self.assertTrue(any("successful record" in p for p in vr.structural(rep)))


class RegistryExecutionSide(unittest.TestCase):
    def run_reg(self, *args):
        return subprocess.run([sys.executable, "-B", str(P / "scripts/registry.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = str(Path(self.tmp.name) / "reg.json")
        # seed an entry at WEIGHTS_AVAILABLE via the discovery-side legal path
        self.run_reg("init", self.reg)
        self.run_reg("add", self.reg, "--id", "m1", "--domain", "mrna", "--task", "te",
                     "--repo", "example.invalid/m1", "--state", "WEIGHTS_AVAILABLE",
                     "--evidence", "fixture weights")

    def tearDown(self):
        self.tmp.cleanup()

    def test_execution_advances_to_installed_then_tested(self):
        for st, ev in [("INSTALLED", "env receipt"), ("EXECUTION_TESTED", "execution report")]:
            r = self.run_reg("transition", self.reg, "m1", st, "--evidence", ev, "--by", "rna-model-execution")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_reg("show", self.reg, "m1")
        self.assertIn("EXECUTION_TESTED", r.stdout)

    def test_production_needs_parent_directive(self):
        # fast-forward with force would be recorded; without force it is refused
        r = self.run_reg("transition", self.reg, "m1", "INSTALLED", "--evidence", "e1")
        self.assertEqual(r.returncode, 0)
        r = self.run_reg("transition", self.reg, "m1", "PRODUCTION_APPROVED")
        self.assertEqual(r.returncode, 2)
        r = self.run_reg("transition", self.reg, "m1", "EXECUTION_TESTED", "--evidence", "e2")
        self.assertEqual(r.returncode, 0)
        r = self.run_reg("transition", self.reg, "m1", "BENCHMARK_VALIDATED", "--evidence", "e3")
        self.assertEqual(r.returncode, 0)
        r = self.run_reg("transition", self.reg, "m1", "PRODUCTION_APPROVED",
                         "--evidence", "e4", "--note", "parent directive 2026-11-17: approved for production use")
        self.assertEqual(r.returncode, 0, r.stdout)
        doc = json.loads(Path(self.reg).read_text(encoding="utf-8-sig"))
        self.assertEqual(doc["entries"]["m1"]["state"], "PRODUCTION_APPROVED")

    def test_validate(self):
        r = self.run_reg("validate", self.reg)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
