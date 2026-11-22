"""Exercise both workflow-review decisions and fail-closed approval handoffs."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from workflow_gate import canonical, decision_schema, load, prepare, screen, sha


class WorkflowGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for kind in ("parameter", "replacement"):
            shutil.copytree(PACKAGE / "tests" / kind, self.root / kind)
        self.select("replacement")

    def select(self, kind):
        self.case = self.root / kind
        self.packet_path = self.case / "packet.json"
        self.packet = load(self.packet_path)

    def write(self, filename, data):
        path = self.case / filename
        path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        return path

    def replace(self, evidence, document):
        row = self.packet["evidence"][evidence]
        row["sha256"] = sha(self.write(row["path"], document))
        if evidence == "workflow":
            self.packet["baseline_sha256"] = row["sha256"]
        self.write("packet.json", self.packet)

    def validate_decision(self, decision=None):
        packet, parents, admitted = prepare(self.packet_path, sha(self.packet_path))
        schema = decision_schema(packet, admitted)
        Draft202012Validator.check_schema(schema)
        decision = load(self.case / "expected.json") if decision is None else decision
        return screen(decision, schema, admitted, parents)

    def test_both_decisions_scope_only_the_affected_stages(self):
        for kind in ("parameter", "replacement"):
            with self.subTest(kind=kind):
                self.select(kind)
                self.assertEqual(self.validate_decision(), {
                    "decision": "propose", "rerun_stages": ["transform", "audit"],
                    "status": "scope_screened", "execution_authorized": False,
                })

    def test_transitive_dependents_follow_topological_order(self):
        workflow = load(self.case / "workflow.json")
        workflow["stages"].append(workflow["stages"][-1] | {
            "id": "release", "inputs": {"verified": "audit.txt"}, "outputs": {"summary": "release.txt"},
        })
        self.replace("workflow", workflow)
        decision = load(self.case / "expected.json") | {"baseline_sha256": self.packet["baseline_sha256"]}
        self.assertEqual(self.validate_decision(decision)["rerun_stages"], ["transform", "audit", "release"])

    def test_wrong_digest_and_evidence_substitution_fail(self):
        dispatch = sha(self.packet_path)
        with self.assertRaisesRegex(ValueError, "frozen dispatch"):
            prepare(self.packet_path, "0" * 64)
        workflow = load(self.case / "workflow.json")
        workflow["stages"][0]["parameters"]["capacity"] = 12
        self.write("workflow.json", workflow)
        with self.assertRaisesRegex(ValueError, "evidence is binary or changed"):
            prepare(self.packet_path, dispatch)
        self.replace("workflow", workflow)
        with self.assertRaisesRegex(ValueError, "frozen dispatch"):
            prepare(self.packet_path, dispatch)

    def test_unsupported_parameter_type_no_op_and_native_limits_fail(self):
        self.select("parameter")
        scope = load(self.case / "scope.json")
        for value, error in ((8, "must change"), ("16", "wire type"), (16.0, "wire type"),
                             (17, "documented request")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, error):
                scope["options"][0]["new"] = value
                self.replace("scope", scope)
                self.validate_decision()

    def test_local_parameter_requires_assigned_value_domain(self):
        self.select("parameter")
        workflow = load(self.case / "workflow.json")
        workflow["stages"][0]["engine"] = "local"
        self.replace("workflow", workflow)
        scope = load(self.case / "scope.json")
        scope["catalog"] = None
        scope["options"][0]["contract"] = "tool-contracts.v1"
        self.replace("scope", scope)
        self.replace("tool-contracts.v1", {"stages": {"transform": {"settings": {"capacity": [8, 16]}}}})
        decision = load(self.case / "expected.json") | {
            "baseline_sha256": self.packet["baseline_sha256"],
            "evidence": ["transform-result", "evaluation", "tool-contracts.v1"],
        }
        self.assertEqual(self.validate_decision(decision)["decision"], "propose")
        scope["options"][0]["new"] = 12
        self.replace("scope", scope)
        with self.assertRaisesRegex(ValueError, "outside the frozen contract"):
            self.validate_decision(decision)

    def test_inactive_and_unknown_tools_fail(self):
        catalog = load(self.case / "tool-contracts.v1.json")
        alternate = "synthetic_text_repair"
        catalog["tools"][alternate]["execution_blocked"] = True
        self.replace("tool-contracts.v1", catalog)
        with self.assertRaisesRegex(ValueError, "explicitly unavailable"):
            self.validate_decision()
        del catalog["tools"][alternate]
        self.replace("tool-contracts.v1", catalog)
        with self.assertRaisesRegex(ValueError, "Unknown Boltzmann job name"):
            self.validate_decision()

    def test_lost_inputs_unmatched_outputs_and_missing_checks_fail(self):
        scope, compatibility = [load(self.case / name) for name in ("scope.json", "compatibility.json")]
        for field, change, error in (
            ("inputs", {}, "same frozen input artifacts"),
            ("outputs", {"filtered_rows": "unmatched.txt"}, "preserve the artifact outputs"),
            ("output_checks", {}, "checks for each replacement output"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, error):
                self.replace("compatibility", compatibility | {field: change})
                options = [scope["options"][0] | {field: change}] if field != "output_checks" else scope["options"]
                self.replace("scope", scope | {"options": options})
                self.validate_decision()

    def test_missing_sources_and_unknown_dependencies_fail(self):
        compatibility = load(self.case / "compatibility.json")
        self.replace("compatibility", compatibility | {"sources": ["unassigned"]})
        with self.assertRaisesRegex(ValueError, "unassigned evidence"):
            self.validate_decision()
        self.replace("compatibility", compatibility)
        workflow = load(self.case / "workflow.json")
        workflow["stages"][2]["inputs"]["rows"] = "missing.txt"
        self.replace("workflow", workflow)
        with self.assertRaisesRegex(ValueError, "without a preceding producer"):
            self.validate_decision()

    def test_no_options_permit_retain_or_blocked_only(self):
        scope = load(self.case / "scope.json")
        self.replace("scope", scope | {"options": []})
        common = {"case_id": self.packet["case_id"], "baseline_sha256": self.packet["baseline_sha256"],
                  "evidence": ["transform-result"], "diagnosis": "Synthetic result.",
                  "success_criterion": "Verify the frozen comparator."}
        for kind, detail in (("retain", {"reversal_criterion": "Fresh evidence."}),
                             ("blocked", {"missing_requirement": "Terminal receipt."})):
            self.assertEqual(self.validate_decision(common | detail | {"decision": kind})["decision"], kind)
        with self.assertRaisesRegex(ValueError, "Invalid document"):
            self.validate_decision()

    def test_second_change_missing_citation_and_numeric_coercion_rejected(self):
        decision = load(self.case / "expected.json")
        for invalid in (
            decision | {"change": [decision["change"], decision["change"]]},
            decision | {"evidence": ["transform-result", "evaluation"]},
            decision | {"change": decision["change"] | {"parameters": {"capacity": 8.0}}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.validate_decision(invalid)

    def test_stub_requires_independent_approval_for_exact_frozen_candidate(self):
        for kind in ("parameter", "replacement"):
            with self.subTest(kind=kind):
                self.select(kind)
                proposal = load(self.case / "expected.json")
                dispatch = sha(self.packet_path)
                packet, parents, admitted = prepare(self.packet_path, dispatch)
                schema = decision_schema(packet, admitted)
                stub_calls = []
                screened = screen(proposal, schema, admitted, parents)
                receipt = {"packet": dispatch, "proposal": canonical(proposal),
                           "rerun_stages": screened["rerun_stages"], "critic": "synthetic-independent",
                           "approved": True}

                def execute_stub(candidate, approval, consent):
                    rerun = screen(candidate, schema, admitted, parents)["rerun_stages"]
                    exact = receipt | {"proposal": canonical(candidate), "rerun_stages": rerun}
                    if not consent or approval != exact or approval["critic"] == "specialist":
                        raise ValueError("No independent and operator-approved exact candidate")
                    stub_calls.extend(rerun)

                for approval, consent in ((None, True), (receipt, False),
                                          (receipt | {"critic": "specialist"}, True),
                                          (receipt | {"approved": False}, True)):
                    with self.assertRaisesRegex(ValueError, "No independent"):
                        execute_stub(proposal, approval, consent)
                modified = deepcopy(proposal)
                modified["diagnosis"] += " Changed after review."
                with self.assertRaisesRegex(ValueError, "No independent"):
                    execute_stub(modified, receipt, True)
                self.assertEqual(stub_calls, [])
                execute_stub(proposal, receipt, True)
                self.assertEqual(stub_calls, ["transform", "audit"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
