import copy
import unittest
from fixtures import task, libraries, row, batch, controlled_histories
from policy import InputError, choose_library, signature, action_signature


class PolicyTests(unittest.TestCase):
    def test_evidence_values_change_untried_choice_with_timing_and_counts_fixed(self):
        t, libs, good, bad = controlled_histories()
        a = choose_library(t, libs, good); b = choose_library(t, libs, bad)
        self.assertEqual((a["library_id"], b["library_id"]), ("LIBRARY_C", "LIBRARY_D"))
        self.assertEqual(choose_library(t, libs, good, "round_robin")["library_id"], "LIBRARY_C")
        self.assertEqual(choose_library(t, libs, bad, "round_robin")["library_id"], "LIBRARY_C")
        self.assertEqual(a["library_states"], b["library_states"])
        self.assertEqual(a["qualifying_ids"], [])
        self.assertEqual(b["qualifying_ids"], [])
        self.assertEqual(a["family_profiles"]["FAMILY_F"]["coverage_vector"], ["4/4", "2/4", "2/4"])
        self.assertEqual(b["family_profiles"]["FAMILY_F"]["coverage_vector"], ["4/4", "1/4", "1/4"])

    def test_tried_actions_are_never_recommended_again(self):
        t, libs, good, _ = controlled_histories()
        d = choose_library(t, libs[:2], good)
        self.assertEqual((d["disposition"], d["reason"], d["library_id"]),
                         ("no_action", "approved_action_set_exhausted", None))

    def test_renamed_identical_library_content_is_not_untried(self):
        t, libs, h, _ = controlled_histories()
        libs[2]["content_sha256"] = libs[0]["content_sha256"]
        d = choose_library(t, libs, h)
        self.assertEqual(d["library_id"], "LIBRARY_D")
        self.assertTrue(d["library_states"]["LIBRARY_C"]["equivalent_content_already_attempted"])

    def test_byte_distinct_but_same_normalized_input_is_not_fresh_material(self):
        t, libs, h, _ = controlled_histories()
        libs[2]["normalized_input_set_sha256"] = libs[0]["normalized_input_set_sha256"]
        d = choose_library(t, libs, h)
        self.assertEqual(d["library_id"], "LIBRARY_D")
        self.assertTrue(d["library_states"]["LIBRARY_C"]["equivalent_normalized_input_already_attempted"])

    def test_different_normalization_policy_cannot_claim_a_new_eligible_asset(self):
        t, libs, h, _ = controlled_histories()
        libs[2]["normalization_policy_id"] = "DIFFERENT_PROFILE"
        d = choose_library(t, libs, h)
        self.assertEqual(d["library_id"], "LIBRARY_D")

    def test_joint_success_stops_before_new_action(self):
        t = task(); libs = libraries()
        d = choose_library(t, libs, [batch(t, libs[0], 1, [row("win", .8, .8)])])
        self.assertEqual((d["disposition"], d["library_id"]), ("stop", None))
        self.assertEqual(d["qualifying_ids"], ["ARTIFICIAL_ID_win"])

    def test_disjoint_marginal_hits_do_not_imply_joint_success(self):
        t, libs, good, _ = controlled_histories()
        d = choose_library(t, libs, good)
        self.assertEqual(d["disposition"], "recommend")
        self.assertEqual(d["qualifying_ids"], [])

    def test_strict_threshold_equalities_never_qualify(self):
        t = task(); libs = libraries()
        rows = [row("a", .6, .8), row("b", .8, .7), row("c", .8, .8, .7)]
        d = choose_library(t, libs, [batch(t, libs[0], 1, rows)])
        self.assertEqual(d["qualifying_ids"], [])
        self.assertEqual(d["family_profiles"]["FAMILY_F"]["coverage_vector"], ["2/3", "1/3", "1/3"])

    def test_terminal_archive_has_no_operational_action(self):
        for state in ("closed", "frozen", "satisfied"):
            t = task(); t["state"] = state
            d = choose_library(t, libraries(), [])
            self.assertEqual((d["disposition"], d["library_id"]), ("not_applicable", None))

    def test_completed_empty_is_not_untried_or_missing(self):
        t = task(); libs = libraries()
        d = choose_library(t, libs, [batch(t, libs[0], 1, [])])
        self.assertEqual(d["library_id"], "LIBRARY_B")
        self.assertEqual(d["library_states"]["LIBRARY_A"]["empty_complete_batches"], 1)
        self.assertEqual(d["family_profiles"], {})

    def test_pending_unknown_failed_never_become_untried(self):
        for status in ("pending", "unknown", "failed"):
            t = task(); libs = libraries()
            d = choose_library(t, libs, [batch(t, libs[0], 9, [], status=status)])
            self.assertNotEqual(d["library_id"], "LIBRARY_A")
            self.assertEqual(d["library_states"]["LIBRARY_A"]["last_sequence"], 9)
            self.assertEqual(d["library_states"]["LIBRARY_A"]["attempts"], 1)
            self.assertEqual(d["family_profiles"], {})

    def test_only_unresolved_attempt_requests_reconciliation(self):
        t = task(); libs = libraries()[:1]
        d = choose_library(t, libs, [batch(t, libs[0], 1, [], status="unknown")])
        self.assertEqual(d["reason"], "reconcile_existing_attempt")

    def test_serial_advisor_waits_even_if_other_untried_assets_exist(self):
        t = task(); libs = libraries()
        d = choose_library(t, libs, [batch(t, libs[0], 1, [], status="pending")])
        self.assertEqual((d["disposition"], d["reason"], d["library_id"]),
                         ("need_information", "reconcile_existing_attempt", None))

    def test_absent_family_evidence_is_explicit_cold_start_not_zero_rate(self):
        d = choose_library(task(), libraries(), [])
        self.assertEqual(d["reason"], "explicit_untried_family_exploration")
        self.assertEqual(d["family_profiles"], {})

    def test_missing_required_score_is_data_quality_failure_not_family_cold_start(self):
        t = task(); libs = libraries(); r = row("missing", .8, .5)
        del r["values"]["objective_b"]
        d = choose_library(t, libs, [batch(t, libs[0], 1, [r])])
        self.assertEqual(d["disposition"], "need_information")
        self.assertEqual(d["family_profiles"], {})

    def test_missing_edit_annotation_does_not_hide_a_counterexample(self):
        t = task(); libs = libraries(); rows = [row("good", .8, .5), row("bad", .4, .5)]
        del rows[1]["edit_family"]
        d = choose_library(t, libs, [batch(t, libs[0], 1, rows)])
        self.assertEqual(d["disposition"], "need_information")
        self.assertEqual(d["family_profiles"], {})

    def test_unreviewed_wrong_parent_context_or_definition_cannot_transfer(self):
        for field, value in (("annotation_reviewed", False), ("parent_id", "OTHER"),
                             ("context_id", "OTHER"), ("family_definition_id", "OTHER")):
            t = task(); libs = libraries(); r = row("a", .8, .5); r[field] = value
            d = choose_library(t, libs, [batch(t, libs[0], 1, [r])])
            self.assertEqual(d["disposition"], "need_information")
            self.assertEqual(d["family_profiles"], {})

    def test_reviewed_multiedit_is_not_evidence_of_isolated_family_effect(self):
        t = task(); libs = libraries(); r = row("multi", .8, .5); r["single_edit"] = False
        d = choose_library(t, libs, [batch(t, libs[0], 1, [r])])
        self.assertEqual(d["family_profiles"], {})
        self.assertEqual(d["library_states"]["LIBRARY_A"]["nonisolated_rows"], 1)

    def test_supplied_identity_required_no_fake_smiles_canonicalisation(self):
        t = task(); libs = libraries(); r = row("a", .8, .5); del r["chemical_id"]
        d = choose_library(t, libs, [batch(t, libs[0], 1, [r])])
        self.assertEqual(d["disposition"], "need_information")

    def test_duplicate_rows_and_batch_replay_do_not_add_independent_support(self):
        t, libs, h, _ = controlled_histories()
        h[0]["rows"] *= 4
        d = choose_library(t, libs, h + [h[0]])
        self.assertEqual(d["family_profiles"]["FAMILY_F"]["reviewed_unique_pairs"], 4)
        self.assertEqual(d["library_states"]["LIBRARY_A"]["attempts"], 1)

    def test_cross_library_same_identity_retains_provenance_but_counts_once(self):
        t = task(); libs = libraries(); r = row("shared", .8, .5)
        d = choose_library(t, libs, [batch(t, libs[0], 1, [r]), batch(t, libs[1], 2, [r])])
        self.assertEqual(d["family_profiles"]["FAMILY_F"]["reviewed_unique_pairs"], 1)
        self.assertEqual(d["cross_library_overlap"], {"ARTIFICIAL_ID_shared": ["LIBRARY_A", "LIBRARY_B"]})

    def test_conflicting_scores_or_family_attribution_abstain(self):
        for changed in (row("shared", .4, .5), row("shared", .8, .5, family="FAMILY_G")):
            t = task(); libs = libraries()
            d = choose_library(t, libs, [batch(t, libs[0], 1, [row("shared", .8, .5)]),
                                        batch(t, libs[1], 2, [changed])])
            self.assertEqual(d["disposition"], "need_information")

    def test_single_vs_multiedit_conflict_cannot_leave_clean_family_support(self):
        t = task(); libs = libraries(); single = row("shared", .8, .5)
        multi = copy.deepcopy(single); multi["single_edit"] = False
        for first, second in ((single, multi), (multi, single)):
            d = choose_library(t, libs, [batch(t, libs[0], 1, [first]), batch(t, libs[1], 2, [second])])
            self.assertEqual(d["disposition"], "need_information")
            self.assertEqual(d["family_profiles"], {})

    def test_immutable_asset_location_content_and_family_card_bound_to_history(self):
        t, libs, h, _ = controlled_histories()
        for field, value in (("asset_ref", "fixture://replacement"), ("content_sha256", "e" * 64),
                             ("target_family", "DIFFERENT_FAMILY"), ("family_definition_id", "NEW_DEFINITION")):
            changed = copy.deepcopy(libs); changed[0][field] = value
            d = choose_library(t, changed, h)
            self.assertEqual(d["disposition"], "need_information")
            self.assertTrue(any("identity_mismatch" in item for item in d["warnings"]))

    def test_comparability_includes_original_reference_assessor_filters_settings_rules(self):
        t, libs, h, _ = controlled_histories()
        for field, value in (("reference_id", "OTHER"), ("assessor_id", "OTHER"),
                             ("generation_settings", {"different": True}), ("filter_protocol", "OTHER")):
            changed = copy.deepcopy(t); changed[field] = value
            self.assertEqual(choose_library(changed, libs, h)["disposition"], "need_information")
        changed = copy.deepcopy(t); changed["constraints"][0]["threshold"] = .2
        self.assertNotEqual(signature(t), signature(changed))

    def test_unapproved_or_unadmitted_source_cannot_establish_success(self):
        t = task(); libs = libraries(); h = [batch(t, libs[0], 1, [row("win", .8, .8)])]
        libs[0]["approved"] = False
        self.assertEqual(choose_library(t, libs, h)["disposition"], "need_information")
        libs[0]["approved"] = True; h[0]["evidence_admissible"] = False
        self.assertEqual(choose_library(t, libs, h)["disposition"], "need_information")

    def test_complete_winner_survives_unrelated_missing_row_but_profiles_do_not(self):
        t = task(); libs = libraries(); bad = row("bad", .4, .5); del bad["values"]["objective_b"]
        d = choose_library(t, libs, [batch(t, libs[0], 1, [row("win", .8, .8), bad])])
        self.assertEqual(d["disposition"], "stop")
        self.assertEqual(d["family_profiles"], {})
        self.assertEqual(d["qualifying_ids"], ["ARTIFICIAL_ID_win"])

    def test_partial_output_does_not_produce_clean_profile(self):
        t = task(); libs = libraries()
        d = choose_library(t, libs, [batch(t, libs[0], 1, [row("a", .8, .5)], complete_output_coverage=False)])
        self.assertEqual(d["disposition"], "need_information")
        self.assertEqual(d["family_profiles"], {})

    def test_bad_destination_cards_or_permissions_are_not_selected(self):
        t, libs, h, _ = controlled_histories()
        for field, value in (("approved", False), ("available_for_analysis", False),
                             ("capability_card_reviewed", False), ("context_id", "OTHER"),
                             ("family_definition_id", "OTHER")):
            changed = copy.deepcopy(libs); changed[2][field] = value
            self.assertEqual(choose_library(t, changed, h)["library_id"], "LIBRARY_D")

    def test_row_and_history_order_do_not_create_evidence_dependent_choice(self):
        t, libs, h, _ = controlled_histories(); swapped = copy.deepcopy(list(reversed(h)))
        for b in swapped: b["rows"].reverse()
        self.assertEqual(choose_library(t, libs, h), choose_library(t, libs, swapped))

    def test_both_strategies_get_identical_data_and_do_not_claim_science(self):
        t, libs, h, _ = controlled_histories()
        a = choose_library(t, libs, h); b = choose_library(t, libs, h, "round_robin")
        self.assertEqual(a["family_profiles"], b["family_profiles"])
        self.assertEqual(a["library_states"], b["library_states"])
        self.assertEqual((a["execution"], a["scientific_benefit"]), ("not_performed", "not_assessed"))
        self.assertFalse(a["resource_limits_enforced"])

    def test_changed_batch_contents_or_missing_asset_digest_rejected(self):
        t = task(); libs = libraries(); one = batch(t, libs[0], 1, [])
        changed = copy.deepcopy(one); changed["rows"] = [row("a", .8, .5)]
        with self.assertRaises(InputError): choose_library(t, libs, [one, changed])
        del libs[0]["content_sha256"]
        with self.assertRaises(InputError): choose_library(t, libs, [])


if __name__ == "__main__":
    unittest.main()
