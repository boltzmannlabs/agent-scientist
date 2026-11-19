"""Unit tests: deterministic router, preflight, dependency plan/verify contract, shared registry CLI."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / "scripts"))
import route_request as rr  # noqa: E402
import dependency_plan as dp  # noqa: E402

CASES = json.loads((P / "tests/cases.json").read_text(encoding="utf-8-sig"))
EXPECTED = json.loads((P / "tests/expected.json").read_text(encoding="utf-8-sig"))


class Router(unittest.TestCase):
    def test_routing_table_cases(self):
        for case, exp in zip(CASES["routing_cases"], EXPECTED["routing_cases"]):
            with self.subTest(case["name"]):
                out = rr.route(case["text"])
                self.assertEqual(out["status"], exp["status"], out)
                if exp.get("leaf"):
                    self.assertEqual(out.get("leaf"), exp["leaf"], out)

    def test_preflight_cases(self):
        for case, exp in zip(CASES["preflight_cases"], EXPECTED["preflight_cases"]):
            with self.subTest(case["name"]):
                out = rr.preflight(case["request"])
                self.assertEqual(out["status"], exp["status"], out)
                self.assertEqual(sorted(out.get("missing_inputs", [])), sorted(exp["missing_inputs"]))
                self.assertFalse(out.get("delegation_started"))

    def test_mechanism_beats_gene(self):
        out = rr.route("CRISPR knockout of a plant gene")
        self.assertEqual(out["leaf"], "application-aware-grna-designer")

    def test_gap_verbs_dominate_design_mentions(self):
        out = rr.route("find an open-source siRNA model with pretrained weights")
        self.assertEqual(out["leaf"], "rna-model-discovery")


class DependencyPlan(unittest.TestCase):
    def test_matrix_loads_and_lists(self):
        names = [l["name"] for l in dp.MATRIX["leaves"]]
        self.assertIn("application-aware-sirna-designer", names)
        self.assertEqual(len(names), 4)

    def test_plan_for_known_leaf(self):
        plan = dp.leaf_plan("rna-model-execution")
        ids = {p["id"] for p in plan["programs"]}
        self.assertIn("git", ids)
        self.assertIn("PLAN_ONLY", plan["note"])

    def test_plan_rejects_unknown(self):
        self.assertIsNone(dp.leaf_plan("no-such-leaf"))

    def test_verify_verdicts_are_valid(self):
        out = json.loads(subprocess.run(
            [sys.executable, "-B", str(P / "scripts/dependency_plan.py"), "--verify", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300).stdout)
        for leaf in out["leaves"]:
            self.assertIn(leaf["verdict"], {"READY", "PARTIAL", "MISSING"})
            for row in leaf["programs"]:
                self.assertTrue(isinstance(row["found"], bool))


class RegistryCLI(unittest.TestCase):
    def test_shared_cli_present_and_consistent(self):
        r = subprocess.run([sys.executable, "-B", str(P / "scripts/registry.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 2)  # no args -> usage error, not crash
        src_disc = (P.parent / "rna-model-discovery/scripts/registry.py").read_text(encoding="utf-8-sig") if (P.parent / "rna-model-discovery/scripts/registry.py").exists() else None
        if src_disc:
            self.assertEqual((P / "scripts/registry.py").read_text(encoding="utf-8-sig"), src_disc,
                             "shared registry CLI copies must stay byte-identical")


class Roster(unittest.TestCase):
    def test_roster_matches_routing_table(self):
        r = subprocess.run([sys.executable, "-B", str(P / "scripts/roster.py"), "check"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["status"], "PASS")

    def test_capabilities_ranks_discovery_for_gap_queries(self):
        r = subprocess.run([sys.executable, "-B", str(P / "scripts/roster.py"), "capabilities",
                            "find a model with pretrained weights for translation efficiency"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ranked = [x["specialist"] for x in json.loads(r.stdout)["ranked"]]
        self.assertIn("rna-model-discovery", ranked[:2])

    def test_describe_unknown_fails(self):
        r = subprocess.run([sys.executable, "-B", str(P / "scripts/roster.py"), "describe", "nope"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
