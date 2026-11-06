"""Behavioral checks for original-reference search evidence and simple controls."""
from copy import deepcopy
import json
import unittest

from rdkit import Chem, DataStructs
from rdkit.Chem import QED, rdFingerprintGenerator

from workflow.search import action_identity, build_search_view, constraint_view


REFERENCE = {"id": "original", "form_id": "original-form", "representation": "CCO"}
OBJECTIVE = {"target_min": 0, "target_max": 3,
             "qed_min_exclusive": QED.qed(Chem.MolFromSmiles("CCO")),
             "similarity_min_exclusive": 0.1,
             "generation_parameters": {"global_models": [
                 {"name": "Lipophilicity", "min_threshold": 0, "max_threshold": 3}]},
             "physical_units": "unverified"}
LIBRARIES = [{"id": "a", "content_sha256": "a" * 64},
             {"id": "b", "content_sha256": "b" * 64}]


def candidate(cid="original", representation="CCO", score=-8):
    return {"candidate_id": cid, "form_id": "original-form" if cid == "original" else "form-" + cid,
            "representation": representation, "values": {"lipophilicity": score}, "status": "completed"}


class SearchTests(unittest.TestCase):
    def view(self, candidates, **kwargs):
        return build_search_view(candidates, reference=REFERENCE, objective=OBJECTIVE,
                                 libraries=kwargs.pop("libraries", LIBRARIES), **kwargs)

    def test_exclusive_boundaries_are_violations_even_when_numeric_gap_zero(self):
        values = {"lipophilicity": 0, "qed": OBJECTIVE["qed_min_exclusive"],
                  "lead_similarity": OBJECTIVE["similarity_min_exclusive"]}
        result = constraint_view(values, OBJECTIVE)
        self.assertEqual(result["gaps"], {"lipophilicity": 0, "qed": 0, "lead_similarity": 0})
        self.assertTrue(result["passes"]["lipophilicity"])
        self.assertFalse(result["passes"]["qed"])
        self.assertFalse(result["passes"]["lead_similarity"])
        self.assertFalse(result["all_constraints_satisfied"])

    def test_original_parent_is_admissible_but_cannot_solve_task(self):
        result = self.view([candidate(score=1)])
        row = result["rows"][0]
        self.assertTrue(row["parent_admissible"])
        self.assertFalse(row["qualified_candidate"])
        self.assertEqual(row["values"]["qed"], OBJECTIVE["qed_min_exclusive"])
        self.assertEqual(result["qualified_candidate_ids"], [])
        self.assertEqual(result["baseline"]["disposition"], "recommend")

    def test_metrics_always_use_original_reference_not_supplied_or_new_parent_values(self):
        supplied = candidate("next", "CCCO", -4)
        supplied["values"].update(qed=1, lead_similarity=1)
        result = self.view([candidate(), supplied])
        row = next(r for r in result["rows"] if r["candidate_id"] == "next")
        self.assertEqual(row["values"]["qed"], QED.qed(Chem.MolFromSmiles("CCCO")))
        self.assertEqual(row["values"]["lead_similarity"], 0.5)
        self.assertNotEqual(row["values"]["lead_similarity"], 1)

    def test_similar_parent_required_and_missing_scores_never_become_options(self):
        rows = [candidate(), candidate("benzene", "c1ccccc1", 1), candidate("missing", "CCCO", None)]
        result = self.view(rows)
        self.assertEqual({a["parent_candidate_id"] for a in result["eligible_actions"]}, {"original"})
        self.assertEqual(next(r for r in result["rows"] if r["candidate_id"] == "missing")["status"], "unresolved")
        self.assertEqual(len(result["rows"]), 3)

    def test_single_joint_success_stops_and_other_candidates_cannot_supply_missing_objectives(self):
        success = self.view([candidate(), candidate("winner", "CCCO", 1)])
        self.assertEqual(success["qualified_candidate_ids"], ["winner"])
        self.assertEqual(success["baseline"]["reason"], "objective_achieved")
        split = self.view([candidate(), candidate("property_only", "CCN", 1), candidate("qed_only", "CCCO", -1)])
        self.assertEqual(split["qualified_candidate_ids"], [])
        self.assertEqual(split["baseline"]["disposition"], "recommend")

    def test_conflicting_and_explicitly_unresolved_exact_forms_are_excluded(self):
        rows = [candidate(), candidate("x", "CCCO", -2), candidate("alias", "OCCC", -3)]
        result = self.view(rows)
        bad = [r for r in result["rows"] if r["candidate_id"] != "original"]
        self.assertTrue(all(r["status"] == "unresolved" for r in bad))
        self.assertEqual({a["parent_candidate_id"] for a in result["eligible_actions"]}, {"original"})
        rows[2]["values"]["lipophilicity"] = -2
        rows[2]["property_prediction_conflict"] = True
        result = self.view(rows)
        self.assertEqual(result["unique_completed_forms"], 1)

    def test_aliases_do_not_duplicate_actions_and_inputs_are_unchanged(self):
        rows = [candidate(), candidate("z", "CCCO", -2), candidate("a", "OCCC", -2)]
        libraries = LIBRARIES + [{"id": "alias-library", "content_sha256": "a" * 64}]
        before = deepcopy((rows, libraries, OBJECTIVE, REFERENCE))
        result = self.view(rows, libraries=libraries)
        self.assertEqual(result["unique_completed_forms"], 2)
        self.assertEqual(len(result["eligible_actions"]), 4)
        self.assertEqual((rows, libraries, OBJECTIVE, REFERENCE), before)
        self.assertEqual(result["baseline"], self.view(list(reversed(rows)), libraries=list(reversed(libraries)))["baseline"])

    def test_attempted_action_blocks_repeat_including_unknown_but_library_reuse_is_allowed(self):
        rows = [candidate(), candidate("next", "CCCO", -2)]
        first = self.view(rows)
        blocked = first["baseline"]["action"]
        attempts = [{"action_key": blocked["action_key"], "state": "submit_unknown"}]
        second = self.view(rows, actions=attempts)
        self.assertNotIn(blocked["action_key"], [a["action_key"] for a in second["eligible_actions"]])
        self.assertTrue(any(a["library_id"] == blocked["library_id"] and
                            a["parent_candidate_id"] != blocked["parent_candidate_id"] for a in second["eligible_actions"]))
        all_attempts = [{"action_key": a["action_key"], "state": "completed"} for a in first["eligible_actions"]]
        self.assertEqual(self.view(rows, actions=all_attempts)["baseline"]["reason"], "no_remaining_admissible_action")

    def test_action_binding_covers_exact_form_objective_anchor_params_and_version(self):
        parent = candidate("p", "CCCO", -2)
        original = action_identity(parent, LIBRARIES[0], OBJECTIVE, original_reference=REFERENCE)
        alias = {**parent, "candidate_id": "different-label", "form_id": "other-label", "representation": "OCCC"}
        self.assertEqual(original, action_identity(alias, LIBRARIES[0], OBJECTIVE, original_reference=REFERENCE))
        variants = [
            action_identity(candidate("p", "CCCCO", -2), LIBRARIES[0], OBJECTIVE, original_reference=REFERENCE),
            action_identity(parent, LIBRARIES[1], OBJECTIVE, original_reference=REFERENCE),
            action_identity(parent, LIBRARIES[0], {**OBJECTIVE, "target_max": 4}, original_reference=REFERENCE),
            action_identity(parent, LIBRARIES[0], OBJECTIVE, original_reference={**REFERENCE, "representation": "CCN"}),
            action_identity(parent, LIBRARIES[0], OBJECTIVE, original_reference=REFERENCE, tool_parameters={"x": 1}),
            action_identity(parent, LIBRARIES[0], OBJECTIVE, original_reference=REFERENCE, tool_version="observed-v2")]
        self.assertNotIn(original, variants)
        stereo = candidate("s", "C[C@H](O)CC", -2)
        other = {**stereo, "representation": "C[C@@H](O)CC"}
        self.assertNotEqual(action_identity(stereo, LIBRARIES[0], OBJECTIVE), action_identity(other, LIBRARIES[0], OBJECTIVE))

    def test_empty_or_invalid_evidence_never_creates_a_scientific_action(self):
        result = self.view([])
        self.assertEqual(result["baseline"]["disposition"], "need_information")
        bad = candidate("bad", "bad-smiles", -2)
        result = self.view([bad, candidate("empty", "", -2)])
        self.assertEqual(result["rows"][0]["status"], "invalid")
        self.assertEqual(result["rows"][1]["status"], "invalid")
        self.assertEqual(result["eligible_actions"], [])
        json.dumps(result, allow_nan=False)

    def test_pareto_tradeoffs_and_diversity_are_separate_from_success(self):
        result = self.view([candidate(), candidate("closer", "CCCO", -1), candidate("higherqed", "CCCCO", -3)])
        self.assertIn("closer", result["pareto_parent_ids"])
        self.assertIn("higherqed", result["pareto_parent_ids"])
        self.assertEqual(result["qualified_candidate_ids"], [])
        self.assertEqual(len(set(result["diversity_representative_ids"])), 3)
        json.dumps(result, allow_nan=False)

    def test_ambiguous_identity_or_nonfinite_objective_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different molecular graphs"):
            self.view([candidate(), {**candidate(), "representation": "CCCO"}])
        with self.assertRaisesRegex(ValueError, "different molecular graphs"):
            self.view([{**candidate(), "representation": "CCCO"}])
        with self.assertRaisesRegex(ValueError, "finite"):
            build_search_view([], reference=REFERENCE, objective={**OBJECTIVE, "target_min": float("nan")}, libraries=LIBRARIES)
        with self.assertRaisesRegex(ValueError, "conflicting contents"):
            self.view([candidate()], libraries=[LIBRARIES[0], {**LIBRARIES[1], "id": "a"}])


if __name__ == "__main__":
    unittest.main()
