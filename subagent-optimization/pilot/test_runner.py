"""State/identity invariants with explicit fixture data, no scientific/model calls."""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pilot.runner import PilotRun


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeAssessor:
    """Synthetic outcomes on ordinary SMILES; not a chemical prediction model."""
    def __init__(self):
        self.calls = 0
        self.received_caches = []

    def assess_csv(self, path, cache=None):
        self.calls += 1
        cache = {} if cache is None else cache
        self.received_caches.append(deepcopy(cache))
        rows, summaries, wins = [], [], []
        new, duplicates = 0, 0
        with Path(path).open() as handle:
            inputs = list(csv.DictReader(handle))
        for index, row in enumerate(inputs, 1):
            form = row["SMILES"]
            cid = "fixture-" + form
            duplicate = form in cache
            duplicates += int(duplicate)
            new += int(not duplicate)
            # Only this explicit test sentinel receives a synthetic success.
            values = {"drd2_p_active": .9 if form == "CCCl" else .2,
                      "qed": .9 if form == "CCCl" else .2, "lead_similarity": .8}
            item = {"candidate_id": cid, "status": "completed", "values": values}
            cache[form] = deepcopy(item)
            summaries.append(item)
            rows.append({"row_index": index, "raw_smiles": form, "candidate_id": cid,
                         "status": "duplicate" if duplicate else "completed"})
            if form == "CCCl":
                wins.append(cid)
        return {"rows": rows, "assessment": {"summaries": summaries}, "cache": cache,
                "new_unique_candidate_evaluations": new, "raw_rows": len(rows),
                "invalid_rows": 0, "duplicate_rows": duplicates,
                "qualified_candidate_ids": wins, "baseline_model_evaluations": 1,
                "artifact_sha256": sha(Path(path)),
                "scorer_kind": "fixture"}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pilot-runner-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assessor = FakeAssessor()
        libraries = []
        for lid, value in (("mixed_reference", "CCO"), ("left", "CCN"), ("right", "CCC")):
            path = self.csv("source-" + lid, [value])
            libraries.append({"id": lid, "csv_path": str(path), "content_sha256": sha(path)})
        lookup = {"mixed_reference": ["a"], "left": ["a", "b"], "right": ["a", "c"]}
        index = {"schema_version": 1, "scope_id": "FIXTURE_SCOPE",
                 "libraries": [{"id": k, "lookup_ids": v} for k, v in lookup.items()],
                 "lookup_dimensions": {k: {"radius": 1, "mode": "GROW"} for k in ("a", "b", "c")}}
        self.protocol = {"schema_version": 1, "scope": "Artificial runner fixture; no scientific comparison",
                         "task_type": "lead_optimization", "arms": ["base", "base_algorithm", "base_algorithm_specialist"],
                         "initial_library_id": "mixed_reference", "libraries": libraries,
                         "reference": {"id": "fixture-lead", "representation": "CCO"},
                         "generation_parameters": {}, "rules": {"fixture": True},
                         "assessor": {"baseline": {"drd2_p_active": .5, "qed": .5, "lead_similarity": 1.0}},
                         "scientific_guidance": "Artificial fixture guidance only.", "resources": {},
                         "lookup_index": index, "routing_policy": {"specialist_name": "smallmol-investigation"},
                         "arm_treatments": {"base": {"provided_coverage_helper": False, "specialist": False},
                                            "base_algorithm": {"provided_coverage_helper": True, "specialist": False},
                                            "base_algorithm_specialist": {"provided_coverage_helper": True, "specialist": True}}}
        self.directory = self.root / "run"
        self.run = PilotRun.create(self.protocol, self.directory, evidence_mode="fixture", assessor=self.assessor)

    def csv(self, name, representations):
        path = self.root / (name + ".csv")
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle); writer.writerow(["SMILES"])
            writer.writerows([value] for value in representations)
        return path

    def state(self):
        return json.loads((self.directory / "state.json").read_text())

    def receipt(self, stage, path):
        request = self.state()["stages"][stage]["request"]
        return {"request_id": request["request_id"], "library_content_sha256": request["library_content_sha256"],
                "status": "completed", "complete_output": True, "job_name": "Fragment_Based_Optimization",
                "doc_id": "FIXTURE-" + stage, "artifact_sha256": sha(path), "evidence_kind": "fixture"}

    def observe(self, stage="common", values=("CCN",)):
        path = self.csv("output-" + stage, values)
        return self.run.ingest(stage, path, self.receipt(stage, path))

    def advice(self, arm, library="left"):
        packet = self.run.decision_context(arm)
        return {"schema_version": 1, "input_digest": packet["input_digest"], "disposition": "recommend",
                "library_id": library, "scientific_question": "Fixture question", "hypothesis": "Fixture hypothesis",
                "competing_explanation": "Fixture competing explanation", "comparison_to_baseline": "Fixture comparison",
                "expected_observation": "Fixture expectation", "reversal_condition": "Fixture reversal",
                "supporting_ids": ["fixture-CCN"], "counterexample_ids": [],
                "limitations": ["Artificial values; no scientific finding."], "information_requests": [],
                "scientific_claim": "hypothesis_only"}

    def test_common_success_stops_before_arms_and_cannot_be_forced_into_comparison(self):
        self.observe(values=("CCCl",))
        next_action = self.run.next()
        self.assertEqual(next_action["phase"], "no_remaining_decision")
        self.assertFalse(next_action["agent_comparison_exercised"])
        with self.assertRaises(ValueError): self.run.decision_context("base")
        report = self.run.report()
        self.assertFalse(report["native_decision_comparison_exercised"])
        self.assertFalse(report["complete_scientific_comparison"])
        self.assertFalse(report["qualified_causal_comparison"])
        self.assertIn("remain unverified", report["comparison_controls"])
        self.assertTrue(all(x["status"] == "not_exercised_common_success" for x in report["arms"].values()))

    def test_development_run_without_property_models_cannot_create_campaign_state(self):
        directory = self.root / "rejected-development-run"
        with self.assertRaisesRegex(ValueError, "at least one"):
            PilotRun.create(self.protocol, directory, evidence_mode="development")
        self.assertFalse(directory.exists())

    def test_evaluation_blocker_prevents_success_and_delegation(self):
        class BlockedAssessor(FakeAssessor):
            def assess_csv(self, path, cache=None):
                batch = super().assess_csv(path, cache)
                batch["evaluation_blockers"] = ["Fixture conflicting reference evidence"]
                return batch
        self.run.assessor = BlockedAssessor()
        self.observe(values=("CCCl",))  # Synthetic success cannot override a blocker.
        self.assertEqual(self.run.next()["phase"], "evaluation_blocked")
        with self.assertRaisesRegex(ValueError, "evaluation blockers"):
            self.run.decision_context("base_algorithm_specialist")
        report = self.run.report()
        self.assertFalse(report["no_remaining_decision"])
        self.assertFalse(report["complete_scientific_comparison"])
        self.assertTrue(report["actual_scientific_stages_once_only"]["common"]["evaluation_blockers"])

    def test_wrong_request_and_changed_bytes_rejected_and_complete_replay_does_not_rescore(self):
        path = self.csv("common-data", ["CCN"])
        receipt = self.receipt("common", path)
        with self.assertRaises(ValueError): self.run.ingest("common", path, {**receipt, "request_id": "wrong"})
        with self.assertRaises(ValueError): self.run.ingest("common", path, {**receipt, "artifact_sha256": "f" * 64})
        self.assertEqual(self.assessor.calls, 0)
        first = self.run.ingest("common", path, receipt)
        replay = self.run.ingest("common", path, receipt)
        self.assertEqual(replay, first)
        self.assertEqual(self.assessor.calls, 1)
        self.assertEqual(self.run.report()["actual_scientific_stages_once_only"]["common"]["effort"]["new_unique_candidate_evaluations"],
                         first["new_unique_candidate_evaluations"])

    def test_imported_specialist_advice_is_routing_failure_without_followup_stage(self):
        self.observe()
        result = self.run.import_decision("base_algorithm_specialist", self.advice("base_algorithm_specialist"))
        self.assertEqual(result["status"], "routing_failure")
        self.assertNotIn("base_algorithm_specialist", self.state()["stages"])
        self.assertFalse(self.run.report()["native_decision_comparison_exercised"])

    def test_retained_connector_output_reports_processing_failure_and_recovers_locally(self):
        class CompletedConnectorFixture:
            def __init__(self): self.calls = []
            def upload(self, request):
                self.calls.append("upload")
                return {"status": "uploaded", "s3_path": "FIXTURE-storage"}
            def submit(self, request, upload):
                self.calls.append("submit")
                return {"status": "accepted", "doc_id": "FIXTURE-common",
                        "job_name": "Fragment_Based_Optimization"}
            def status(self, request, submit):
                self.calls.append("status")
                return {"status": "completed", "doc_id": "FIXTURE-common",
                        "job_name": "Fragment_Based_Optimization"}
        adapter = CompletedConnectorFixture()
        self.run.dispatch("common", adapter)
        self.run.monitor("common", adapter)
        path = self.csv("retained-output", ["CCN"])
        receipt = {**self.receipt("common", path), "evidence_kind": "existing_connector_runtime"}
        original_assess = self.assessor.assess_csv
        def fail_processing(path, cache=None):
            raise RuntimeError("Fixture local processing failure")
        self.assessor.assess_csv = fail_processing
        with self.assertRaisesRegex(RuntimeError, "local processing failure"):
            self.run.ingest("common", path, receipt)
        self.assertIsNone(self.state()["stages"]["common"]["batch"])
        report = self.run.report()
        self.assertEqual(report["actual_scientific_stages_once_only"]["common"]["status"], "processing_failed")
        self.assertIsNone(report["actual_scientific_stages_once_only"]["common"]["effort"])
        self.assertFalse(report["complete_scientific_comparison"])
        self.assertFalse(report["qualified_causal_comparison"])
        self.assessor.assess_csv = original_assess
        self.run.recover("common")
        self.assertEqual(self.state()["stages"]["common"]["status"], "complete")
        self.assertEqual(adapter.calls, ["upload", "submit", "status"])

    def test_coherent_request_substitution_cannot_change_initial_or_selected_library(self):
        state = self.state()
        original = deepcopy(state)
        state["stages"]["common"]["request"] = self.run._expected_request(state, "common", "left")
        (self.directory / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "Stored request differs"):
            PilotRun(self.directory, assessor=self.assessor).next()
        (self.directory / "state.json").write_text(json.dumps(original))
        self.observe()
        self.run.import_decision("base", self.advice("base", "left"))
        state = self.state()
        original = deepcopy(state)
        state["stages"]["base"]["request"] = self.run._expected_request(state, "base", "right")
        (self.directory / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "Stored request differs"):
            PilotRun(self.directory, assessor=self.assessor).next()
        state = deepcopy(original)
        state["decisions"]["base"]["status"] = "routing_failure"
        (self.directory / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "validated library recommendation"):
            PilotRun(self.directory, assessor=self.assessor).next()
        (self.directory / "state.json").write_text(json.dumps(original))
        self.assertEqual(self.run.next()["phase"], "conditional_decisions")

    def test_ambiguous_submit_is_persisted_before_call_and_blocks_repeat_after_reopen(self):
        run = self.run
        class UnknownSubmission:
            def __init__(self): self.uploads = self.submissions = 0
            def upload(self, request):
                self.uploads += 1
                return {"status": "uploaded", "s3_path": "FIXTURE-storage"}
            def submit(self, request, upload):
                self.submissions += 1
                persisted = json.loads((run.directory / "state.json").read_text())
                if persisted["stages"]["common"]["status"] != "submitting":
                    raise AssertionError("Submission intent not durable before callback")
                raise TimeoutError("Fixture uncertain outcome after dispatch")
        adapter = UnknownSubmission()
        with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            self.run.dispatch("common", adapter)
        self.assertEqual(self.state()["stages"]["common"]["status"], "submit_unknown")
        reopened = PilotRun(self.directory, assessor=self.assessor)
        with self.assertRaisesRegex(ValueError, "reconciled"):
            reopened.dispatch("common", adapter)
        self.assertEqual((adapter.uploads, adapter.submissions), (1, 1))

    def test_followup_caches_share_only_common_observations_without_cross_arm_leakage(self):
        self.observe()
        original_common = deepcopy(self.state()["stages"]["common"]["batch"]["cache"])
        self.run.import_decision("base", self.advice("base", "left"))
        self.run.import_decision("base_algorithm", self.advice("base_algorithm", "right"))
        self.observe("base", ("CCC",))
        self.observe("base_algorithm", ("CCF",))
        state = self.state()
        self.assertEqual(state["stages"]["common"]["batch"]["cache"], original_common)
        self.assertEqual(self.assessor.received_caches[1], original_common)
        self.assertEqual(self.assessor.received_caches[2], original_common)
        self.assertNotIn("CCC", state["stages"]["base_algorithm"]["batch"]["cache"])
        self.assertNotIn("CCF", state["stages"]["base"]["batch"]["cache"])


if __name__ == "__main__":
    unittest.main()
