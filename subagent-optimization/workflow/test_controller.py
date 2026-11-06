"""Complete controller chains with real environment state and fixture science."""

import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
from workflow.admission import APPROVED_WARNING
from workflow.context import episode_context
from workflow.controller import advance, collect
from workflow.session import WorkflowSession
from workflow import test_session as fixtures


class FixtureDispatcher:
    """Explicit synthetic connector: never network, prediction or native LLM evidence."""

    def __init__(self):
        self.calls = []
        self.pending = False
        self.fail_download_once = False

    def validate(self, stage, args):
        return {"warnings": [APPROVED_WARNING], "errors": []}

    def __call__(self, name, args):
        self.calls.append((name, args))
        if name == "boltzmann_upload":
            return {
                "status": "uploaded",
                "sha256": hashlib.sha256(
                    Path(args["local_path"]).read_bytes()
                ).hexdigest(),
                "s3_path": "fixture-storage/library",
            }
        if name == "boltzmann_submit":
            return {
                "status": "accepted",
                "job_name": args["job_name"],
                "doc_id": "FIXTURE-JOB",
            }
        if name == "boltzmann_status":
            if self.pending:
                return {
                    "status": "unknown",
                    "service_status": "pending",
                    "error": "job pending",
                    **args,
                }
            return {
                "status": "Success",
                **args,
                "OutputData": {
                    "output_path": {
                        "download_link": [
                            "https://fixture.invalid/"
                            + str(sum(n == "boltzmann_status" for n, a in self.calls))
                            + ".csv"
                        ]
                    }
                },
            }
        if name == "boltzmann_download":
            if self.fail_download_once:
                self.fail_download_once = False
                return {"error": "EXPIRED_FIXTURE_LINK", "output_paths": []}
            folder = Path(args["output_folder"])
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "generated_mols.csv"
            path.write_text("SMILES,Lipophilicity\nCCO,-1\nCCN,-2\n")
            return {"status": "downloaded", "output_paths": [str(path)], "errors": []}
        raise AssertionError("Unexpected tool " + name)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SessionTests(
            "test_restart_and_episode_allowance_do_not_reset"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.session = self.fixture.create()
        self.dispatch = FixtureDispatcher()

    def episode(self):
        assignment = episode_context(
            self.session,
            {
                "execution_mode": "host_mediated",
                "job_name": "Fragment_Based_Optimization",
            },
        )
        action = assignment["helper_summaries"]["eligible_actions"][0]
        outcome = {
            "schema_version": 1,
            "assignment_id": assignment["assignment_id"],
            "episode_id": assignment["episode_id"],
            "input_digest": assignment["input_digest"],
            "status": "action_requested",
            "chosen_action": {
                "kind": "generate",
                "parent_id": action["parent_candidate_id"],
                "library_id": action["library_id"],
                "action_key": action["action_key"],
            },
            "evidence_ids": [self.fixture.reference["id"]],
            "final_candidate_ids": [],
            "pending_jobs": [],
            "artifact_refs": [],
            "rationale": "ENGINEERING FIXTURE: test original-reference neighborhood.",
            "stop_reason": "Host action requested.",
            "limitations": ["Synthetic transport/controller evidence only"],
            "information_requests": [],
        }
        return assignment, {
            "validation_status": "passed",
            "mode": "host_mediated",
            "outcome": outcome,
        }

    def test_generate_wait_collect_assess_resume_without_repeating_science(self):
        assignment, result = self.episode()
        accepted = advance(self.session, assignment, result, self.dispatch)
        self.assertEqual(accepted["phase"], "waiting")
        self.dispatch.pending = True
        self.assertEqual(collect(self.session, self.dispatch)[0]["phase"], "waiting")
        self.assertEqual(
            len([n for n, a in self.dispatch.calls if n == "boltzmann_submit"]), 1
        )
        self.dispatch.pending = False
        checked = collect(self.session, self.dispatch)
        self.assertEqual(checked[0]["phase"], "observations_ready")
        self.assertEqual(checked[0]["assessment"]["raw_rows"], 2)
        reopened = WorkflowSession(self.session.store, self.session.assignment_id)
        self.assertEqual(reopened.attempts()[0]["state"], "complete")
        self.assertEqual(collect(reopened, self.dispatch), [])
        self.assertEqual(
            len([n for n, a in self.dispatch.calls if n == "boltzmann_submit"]), 1
        )
        later = episode_context(reopened, {"execution_mode": "host_mediated"})
        self.assertNotEqual(later["episode_id"], assignment["episode_id"])
        self.assertEqual(later["resources"]["episodes_started"], 2)
        self.assertNotEqual(
            later["evidence_snapshot_digest"], assignment["evidence_snapshot_digest"]
        )
        self.assertEqual(later["prior_actions"][0]["assessment"]["raw_rows"], 2)

    def test_expired_download_refreshes_same_job_without_new_science(self):
        assignment, result = self.episode()
        advance(self.session, assignment, result, self.dispatch)
        self.dispatch.fail_download_once = True
        self.assertEqual(
            collect(self.session, self.dispatch)[0]["phase"], "results_ready"
        )
        self.assertEqual(
            collect(self.session, self.dispatch)[0]["phase"], "observations_ready"
        )
        statuses = [a for n, a in self.dispatch.calls if n == "boltzmann_status"]
        downloads = [a for n, a in self.dispatch.calls if n == "boltzmann_download"]
        self.assertEqual(len(statuses), 2)
        self.assertNotEqual(downloads[0]["download_url"], downloads[1]["download_url"])
        self.assertEqual(
            len([n for n, a in self.dispatch.calls if n == "boltzmann_submit"]), 1
        )

    def test_pending_work_cannot_be_hidden_by_final_freeze(self):
        assignment, result = self.episode()
        advance(self.session, assignment, result, self.dispatch)
        with self.assertRaises(ValueError):
            self.session.finish([], "Fixture stop")
        collect(self.session, self.dispatch)
        self.session.finish([], "No qualifying fixture candidate")
        self.assertTrue(self.session.report()["freezes"])

    def test_row_accounting_recovers_before_completion_without_duplicate_jobs(self):
        assignment, result = self.episode()
        advance(self.session, assignment, result, self.dispatch)
        original = self.session.store.dispatch

        def fail_usage(op, *args, **kwargs):
            if op == "usage" and args[-1].get("unit") == "returned_rows":
                raise RuntimeError("FIXTURE bookkeeping interruption")
            return original(op, *args, **kwargs)

        with patch.object(self.session.store, "dispatch", side_effect=fail_usage):
            with self.assertRaises(RuntimeError):
                collect(self.session, self.dispatch)
        self.assertEqual(self.session.attempts()[0]["state"], "downloaded")
        self.assertEqual(
            collect(self.session, self.dispatch)[0]["phase"], "observations_ready"
        )
        rows = [
            u for u in self.session.report()["usage"] if u["unit"] == "returned_rows"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 2)
        self.assertEqual(
            len([n for n, a in self.dispatch.calls if n == "boltzmann_submit"]), 1
        )

    def test_display_aliases_are_stabilized_in_persistent_decision_history(self):
        from copy import deepcopy
        from workflow.identifiers import present_assignment, expand_outcome

        assignment, result = self.episode()
        wire, manifest = present_assignment(assignment)
        selected = wire["helper_summaries"]["eligible_actions"][0]
        outcome = deepcopy(result["outcome"])
        outcome["input_digest"] = wire["input_digest"]
        outcome["chosen_action"].update(
            parent_id=selected["parent_candidate_id"],
            library_id=selected["library_id"],
            action_key=selected["action_key"],
        )
        outcome["rationale"] = (
            "Inspect action "
            + selected["action_key"]
            + " using the actual fixture observations."
        )
        result.update(
            wire_outcome=outcome,
            identifier_alias_manifest=manifest,
            outcome=expand_outcome(outcome, manifest),
        )
        advance(self.session, assignment, result, self.dispatch)
        actual = self.session.report()["decisions"][0]
        self.assertIn(
            result["outcome"]["chosen_action"]["action_key"], actual["rationale"]
        )
        later = episode_context(self.session, {"execution_mode": "host_mediated"})
        self.assertEqual(
            later["helper_summaries"]["scientific_decisions"][0]["rationale"],
            actual["rationale"],
        )
        links = later["helper_summaries"]["historical_prose_reference_map"]
        self.assertTrue(
            any(r.get("action_key") == actual["next_action"] for r in links)
        )

    def test_stale_or_blocked_advice_cannot_submit(self):
        assignment, result = self.episode()
        result["mode"] = "planning_only"
        with self.assertRaises(ValueError):
            advance(self.session, assignment, result, self.dispatch)
        result["mode"] = "host_mediated"
        result["outcome"]["status"] = "blocked"
        self.assertEqual(
            advance(self.session, assignment, result, self.dispatch)["phase"], "blocked"
        )
        self.assertEqual(self.dispatch.calls, [])

    def test_failed_local_check_recovers_original_known_unsent_reservation(self):
        original = self.session.store.dispatch

        def fail_check(op, *args, **kwargs):
            if op == "check":
                raise RuntimeError("fixture check failed")
            return original(op, *args, **kwargs)

        with patch.object(self.session.store, "dispatch", side_effect=fail_check):
            with self.assertRaises(RuntimeError):
                self.session.reserve(self.fixture.reference["id"], "a")
        first = self.session.attempts()[0]
        recovered = WorkflowSession(
            self.session.store, self.session.assignment_id
        ).reserve(self.fixture.reference["id"], "a")
        self.assertEqual(first["action_key"], recovered["action_key"])
        self.assertEqual(len(self.session.attempts()), 1)
        self.assertEqual(self.dispatch.calls, [])


if __name__ == "__main__":
    unittest.main()
