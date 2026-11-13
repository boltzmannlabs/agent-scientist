from copy import deepcopy
import math
import unittest

from fixtures import action, candidate, config, panel_rows, snapshot
from feedback_policy import (InputError, action_key, assessment_subset, classify_batch,
                             decide, select_panel, summarize_final)


class Decisions(unittest.TestCase):
    def setUp(self):
        self.config = config()
        self.cards = [action("crem"), action("graph_ga")]

    def decide(self, state=None, cards=None):
        return decide(snapshot() if state is None else state,
                      self.cards if cards is None else cards, self.config)

    def test_feasible_lead_without_new_candidates_does_not_invent_solubility_deficit(self):
        decision = self.decide()
        self.assertEqual(decision["chosen"]["route"], "crem")
        self.assertEqual(decision["reason"], "eligible_parent_docking_hypothesis")
        self.assertEqual(decision["observations"]["solubility_only_failures"], [])
        self.assertEqual(decision["execution"], "not_performed")
        self.assertEqual(decision["scientific_benefit"], "not_assessed")

    def test_measured_solubility_deficit_changes_choice_with_same_cards(self):
        state = snapshot([candidate(), candidate("NEW", role="generated", sol=-6)])
        decision = self.decide(state)
        self.assertEqual(decision["chosen"]["route"], "graph_ga")
        self.assertEqual(decision["reason"], "measured_solubility_deficit")
        self.assertEqual(decision["observations"]["solubility_only_failures"], ["NEW"])

    def test_missing_predictions_failed_docking_or_control_are_not_solubility_failure(self):
        for row in (candidate("NEW", role="generated", sol=None),
                    candidate("NEW", role="generated", vina=None),
                    candidate("FIXTURE_CONTROL", role="control", sol=-7)):
            with self.subTest(row=row):
                decision = self.decide(snapshot([candidate(), row]))
                self.assertEqual(decision["chosen"]["route"], "crem")
                self.assertEqual(decision["observations"]["solubility_only_failures"], [])

    def test_full_eligible_pool_keeps_quality_search_despite_other_solubility_failures(self):
        rows = [candidate(), *panel_rows(), candidate("BAD_SOL", role="generated", sol=-8)]
        decision = self.decide(snapshot(rows))
        self.assertEqual(decision["chosen"]["route"], "crem")
        self.assertEqual(decision["disposition"], "RECOMMEND")

    def test_missing_parent_evidence_can_select_existing_assessment(self):
        state = snapshot([candidate(sol=None)])
        decision = self.decide(state, [*self.cards, action("assess")])
        self.assertEqual(decision["chosen"]["route"], "assess")
        self.assertEqual(decision["reason"], "resolve_parent_evidence")
        self.assertEqual(self.decide(state)["disposition"], "NEEDS_EVIDENCE")

    def test_feasible_parent_missing_docking_does_not_use_known_infeasible_parent(self):
        state = snapshot([candidate(vina=None), candidate("BAD", role="generated", sol=-6)])
        decision = self.decide(state, [action("graph_ga", "BAD"), action("assess")])
        self.assertEqual(decision["chosen"]["route"], "assess")

    def test_unknown_predictor_is_not_qualified_by_valid_payload(self):
        state = snapshot([candidate(), candidate("BAD", role="generated", sol=-6)])
        cards = deepcopy(self.cards)
        cards[1]["objective_qualified"] = False
        decision = self.decide(state, cards)
        self.assertEqual(decision["chosen"]["route"], "crem")
        self.assertIn("hosted_objective_unresolved", [r["reason"] for r in decision["rejected"]])
        self.assertIsNone(self.decide(state, cards[1:])["chosen"])

    def test_unknown_method_or_wrong_units_do_not_pass_as_zero_or_as_log_solubility(self):
        for key, value in (("method", "DIFFERENT_MODEL"), ("unit", "mg/mL"),
                           ("value", math.inf), ("value", math.nan)):
            row = candidate()
            row["measurements"]["solubility"][key] = value
            decision = self.decide(snapshot([row]), [*self.cards, action("assess")])
            self.assertEqual(decision["chosen"]["route"], "assess")
            self.assertEqual(decision["observations"]["solubility_only_failures"], [])

    def test_pending_and_ambiguous_acceptance_preserve_receipts_and_prevent_new_action(self):
        for status in ("pending", "running", "acceptance_unknown"):
            state = snapshot()
            state["jobs"] = [{"id": "original-job", "status": status}]
            original = deepcopy(state)
            decision = self.decide(state)
            self.assertEqual((decision["disposition"], decision["job_ids"]), ("WAIT", ["original-job"]))
            self.assertEqual(state, original)

    def test_final_reserve_search_cap_and_generation_cap(self):
        state = snapshot()
        state["resources"]["final_remaining"] = 9
        self.assertEqual(self.decide(state)["reason"], "insufficient_final_reserve")
        state = snapshot()
        state["resources"]["search_remaining"] = 9
        self.assertIsNone(self.decide(state)["chosen"])
        state = snapshot()
        state["resources"]["generation_remaining"] = 0
        self.assertIsNone(self.decide(state)["chosen"])

    def test_invalid_allowances_are_rejected_instead_of_invented(self):
        for invalid in (-1, math.inf, None, True, "100"):
            state = snapshot()
            state["resources"]["search_remaining"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(InputError):
                self.decide(state)
        card = action()
        card["search_allocation"] = -1
        self.assertIsNone(self.decide(cards=[card])["chosen"])

    def test_terminal_or_declared_stopping_rule_stops_but_properties_alone_do_not(self):
        for status in ("closed", "frozen", "completed"):
            state = snapshot()
            state["state"] = status
            self.assertEqual(self.decide(state)["reason"], "task_terminal")
        state = snapshot()
        state["stopping_condition_met"] = True
        self.assertEqual(self.decide(state)["reason"], "declared_stopping_condition_met")
        self.assertEqual(self.decide()["disposition"], "RECOMMEND")

    def test_public_payloads_do_not_acquire_unsupported_edit_masks_or_parent(self):
        for field, value in (("protected_atoms", [1, 2]), ("ref_mol", "OTHER")):
            card = action()
            card["payload"][field] = value
            self.assertIsNone(self.decide(cards=[card])["chosen"])
        cards = deepcopy(self.cards)
        cards[1]["payload"].pop("global_models")
        self.assertIsNone(self.decide(cards=cards[1:])["chosen"])

    def test_parent_prefers_feasible_lower_vina_score(self):
        state = snapshot([candidate(), candidate("BETTER", role="generated", vina=-9),
                          candidate("INFEASIBLE", role="generated", vina=-20, sol=-8)])
        cards = [action("crem", row["identity"]) for row in state["candidates"]]
        self.assertEqual(self.decide(state, cards)["chosen"]["parent_identity"], "BETTER")

    def test_nondominated_parent_frontier_keeps_incompatible_units_separate(self):
        rows = [candidate(sol=-6), candidate("OTHER", role="generated", qed=.3),
                candidate("DOMINATED", role="generated", qed=.2, sol=-7)]
        cards = [action("crem", row["identity"]) for row in rows]
        decision = self.decide(snapshot(rows), cards)
        self.assertEqual(set(decision["observations"]["admissible_parents"]), {"FIXTURE_LEAD", "OTHER"})
        self.assertNotEqual(decision["chosen"]["parent_identity"], "DOMINATED")

    def test_explicit_constraint_priority_selects_within_frontier(self):
        self.config["constraint_priorities"] = ["qed"]
        rows = [candidate(sol=-6), candidate("OTHER", role="generated", qed=.3)]
        cards = [action("crem", row["identity"]) for row in rows]
        self.assertEqual(self.decide(snapshot(rows), cards)["chosen"]["parent_identity"], "FIXTURE_LEAD")

    def test_row_card_order_and_display_names_do_not_change_scientific_choice(self):
        state = snapshot([candidate(), candidate("BAD", role="generated", sol=-6)])
        original = self.decide(state)
        state["candidates"].reverse()
        cards = deepcopy(list(reversed(self.cards)))
        for i, card in enumerate(cards):
            card["display_id"] = "renamed-%s" % i
        for i, row in enumerate(state["candidates"]):
            row["display_id"] = "renamed-row-%s" % i
        changed = self.decide(state, cards)
        self.assertEqual(original["chosen"]["action_key"], changed["chosen"]["action_key"])
        self.assertEqual(original["observations"], changed["observations"])

    def test_aliases_and_extra_libraries_do_not_bias_route_weight(self):
        # Confounded failures yield no route-specific preference: explicit exploration.
        state = snapshot([candidate(sol=-6, qed=.3)])
        alias = action()
        alias["profile_id"] = "ALIAS_PROFILE_LABEL"
        alias["payload"]["library_path"] = "fixture://another-handle-for-same-set"
        self.assertEqual(action_key(alias), action_key(self.cards[0]))
        additional = action()
        additional["library_identity"] = "DIFFERENT_FIXTURE_LIBRARY"
        for seed in range(40):
            self.config["seed"] = seed
            original = self.decide(state)
            aliased = self.decide(state, [*self.cards, alias])
            expanded = self.decide(state, [*self.cards, additional])
            self.assertEqual(original["reason"], "explicit_exploration")
            self.assertEqual(original["chosen"]["action_key"], aliased["chosen"]["action_key"])
            self.assertEqual(original["chosen"]["route"], expanded["chosen"]["route"])

    def test_conflicting_alias_targets_are_not_row_order_dependent(self):
        alias = action()
        alias["targets"] = ["qed"]
        with self.assertRaises(InputError):
            self.decide(cards=[action(), alias])

    def test_computed_action_key_cannot_be_overwritten_by_caller(self):
        card = action()
        card["action_key"] = "STALE_CALLER_KEY"
        decision = self.decide(cards=[card])
        self.assertEqual(decision["chosen"]["action_key"], action_key(card))

    def test_replication_allowed_but_fixed_seed_repeat_not_called_stochastic_exploration(self):
        card = action()
        state = snapshot()
        state["attempted_action_keys"] = [action_key(card)]
        self.assertIsNone(self.decide(state, [card])["chosen"])
        card["repeat"] = "replication"
        self.assertEqual(self.decide(state, [card])["disposition"], "RECOMMEND")
        card["repeat"] = "stochastic_resampling"
        self.assertIsNone(self.decide(state, [card])["chosen"])
        card["stochasticity_verified"] = True
        self.assertEqual(self.decide(state, [card])["disposition"], "RECOMMEND")

    def test_decision_does_not_mutate_inputs_or_spend_allowance(self):
        state = snapshot()
        before = deepcopy((state, self.cards, self.config))
        self.decide(state)
        self.assertEqual((state, self.cards, self.config), before)


class SharedEvaluation(unittest.TestCase):
    def setUp(self):
        self.config = config()

    def test_feasibility_first_panel_excludes_better_scoring_infeasible_and_recovered_references(self):
        rows = [*panel_rows(), candidate("FAIL", role="generated", sol=-8, vina=-30),
                candidate("UNKNOWN", role="generated", sol=None, vina=-40),
                candidate("FIXTURE_LEAD", role="generated", vina=-50),
                candidate("FIXTURE_CONTROL", role="generated", vina=-60)]
        rows.append(deepcopy(rows[0]))
        panel = select_panel(rows, self.config)
        self.assertEqual(panel["identities"], [r["identity"] for r in panel_rows()])
        self.assertEqual(panel, select_panel(list(reversed(rows)), self.config))

    def test_exact_inclusive_property_boundaries_and_canonical_ties(self):
        rows = [candidate("B", role="generated", sol=-4, qed=.5, logp=0),
                candidate("A", role="generated", sol=-4, qed=.5, logp=5)]
        panel = select_panel(rows, self.config)
        self.assertEqual(panel["identities"][:2], ["A", "B"])
        self.assertEqual(panel["identities"][2:], [None] * 8)

    def test_final_failure_or_missing_slot_cannot_be_replaced_or_hidden_by_mean(self):
        rows = panel_rows()
        panel = select_panel(rows, self.config)
        rows[0]["measurements"]["vina"]["status"] = "failed"
        rows.append(candidate("EXTRA", role="generated", vina=-50))
        result = summarize_final(panel, rows, self.config)
        self.assertEqual(result["successful_slots"], 9)
        self.assertIsNone(result["mean_native_vina"])
        self.assertEqual(result["status"], "INCOMPLETE_EVALUATION")
        sparse = select_panel(rows[1:5], self.config)
        self.assertIsNone(summarize_final(sparse, panel_rows(), self.config)["mean_native_vina"])

    def test_complete_final_panel_losing_constraint_does_not_become_a_joint_success(self):
        rows = panel_rows()
        panel = select_panel(rows, self.config)
        rows[0]["measurements"]["solubility"]["value"] = -7
        result = summarize_final(panel, rows, self.config)
        self.assertEqual((result["status"], result["qualifying_slots"]), ("COMPLETE", 9))
        self.assertFalse(result["all_eligible"])
        self.assertAlmostEqual(result["mean_native_vina"], -9.55)

    def test_panel_tampering_and_conflicting_duplicate_measurements_rejected(self):
        rows = panel_rows()
        panel = select_panel(rows, self.config)
        panel["identities"].reverse()
        with self.assertRaises(InputError):
            summarize_final(panel, rows, self.config)
        conflicting = deepcopy(rows[0])
        conflicting["measurements"]["qed"]["value"] = .9
        with self.assertRaises(InputError):
            select_panel(rows + [conflicting], self.config)

    def test_assessment_subset_is_capped_seeded_and_order_duplicate_invariant(self):
        ids = ["I%s" % i for i in range(30)]
        chosen = assessment_subset(ids, 7, 123)
        self.assertEqual(len(chosen), 7)
        self.assertEqual(chosen, assessment_subset(list(reversed(ids)) + ids[:4], 7, 123))
        self.assertEqual(assessment_subset(ids, 0, 123), [])
        self.assertEqual(len(assessment_subset(ids, 100, 123)), 30)


class Feedback(unittest.TestCase):
    def setUp(self):
        self.config = config()

    def classify(self, before, returned, objective=True, change=True):
        return classify_batch(before, returned, self.config, objective_active=objective,
                              intended_change_observed=change)

    def test_non_best_molecule_can_improve_complete_retained_panel_mean(self):
        before = panel_rows()
        result = self.classify(before, [candidate("NEW", role="generated", vina=-9.95)])
        self.assertTrue(result["retained_pool_quality_progress"])
        self.assertTrue(result["progress"])
        self.assertFalse(result["coverage_progress"])
        self.assertLess(result["retained_pool_mean_after"], result["retained_pool_mean_before"])

    def test_novel_nonimproving_and_duplicate_only_are_different_feedback(self):
        before = panel_rows()
        novel = self.classify(before, [candidate("NEW", role="generated", vina=-1)])
        duplicate = self.classify(before, [deepcopy(before[0])])
        self.assertFalse(novel["progress"])
        self.assertTrue(novel["counterevidence"])
        self.assertFalse(novel["no_new_information"])
        self.assertTrue(duplicate["no_new_information"])
        self.assertFalse(duplicate["counterevidence"])

    def test_progress_counterevidence_and_missing_evidence_can_coexist(self):
        returned = [candidate("NEW", role="generated", vina=-12),
                    candidate("MISSING", role="generated", sol=None)]
        result = self.classify(panel_rows(), returned, change=False)
        self.assertTrue(result["progress"])
        self.assertTrue(result["counterevidence"])
        self.assertTrue(result["unresolved_evidence"])

    def test_lead_control_recoveries_do_not_count_as_new_eligible_progress(self):
        for identity, role in (("FIXTURE_LEAD", "lead"), ("FIXTURE_CONTROL", "control"),
                               ("OTHER_HISTORICAL_LEAD", "lead")):
            before = [candidate(identity, role=role)]
            returned = [candidate(identity, role="generated")]
            result = self.classify(before, returned)
            self.assertFalse(result["coverage_progress"])
            self.assertFalse(result["progress"])

    def test_unknown_objective_or_missing_intended_change_remains_unresolved(self):
        for objective, change in ((None, True), (False, True), (True, None)):
            result = self.classify([], [candidate("NEW", role="generated")], objective, change)
            self.assertTrue(result["unresolved_evidence"])

    def test_extra_eligible_candidates_after_full_panel_are_not_coverage_progress(self):
        result = self.classify(panel_rows(), [candidate("NEW", role="generated", vina=-1)])
        self.assertFalse(result["coverage_progress"])

    def test_partial_duplicate_does_not_erase_retained_complete_observation(self):
        before = panel_rows()
        partial = deepcopy(before[0])
        partial["measurements"]["solubility"]["status"] = "unavailable"
        partial["measurements"]["solubility"]["value"] = None
        result = self.classify(before, [partial])
        self.assertEqual(result["retained_pool_mean_before"], result["retained_pool_mean_after"])
        self.assertTrue(result["unresolved_evidence"])
        self.assertEqual(result["unresolved_observation_conflicts"], [before[0]["identity"]])

    def test_conflicting_rescore_cannot_become_new_chemistry_or_pool_gain(self):
        before = panel_rows()
        rescored = deepcopy(before[0])
        rescored["measurements"]["vina"]["value"] = -100
        result = self.classify(before, [rescored])
        self.assertFalse(result["progress"])
        self.assertFalse(result["no_new_information"])
        self.assertTrue(result["unresolved_evidence"])
        self.assertEqual(result["retained_pool_mean_before"], result["retained_pool_mean_after"])


if __name__ == "__main__":
    unittest.main()
