import copy
import unittest

from prototype.context_contract.context_contract import ContractError, digest
from prototype.library_policy.fixtures import row, batch
from specialist.advisor import prepare, accept, parse_answer
from specialist.fixtures import source, canned_answer


class AdvisorTests(unittest.TestCase):
    def test_packet_retains_full_supplied_cohort_rules_and_resource_unknowns(self):
        s = source(); before = copy.deepcopy(s); a = prepare(s)
        self.assertEqual(a["status"], "invoke")
        self.assertEqual(a["packet"]["task"], s["task"])
        self.assertEqual(a["packet"]["batches"], s["batches"])
        self.assertEqual(a["packet"]["resource_summary"], s["resource_summary"])
        self.assertEqual(a["packet"]["eligible_library_ids"], ["LIBRARY_C", "LIBRARY_D"])
        self.assertEqual(s, before)

    def test_terminal_success_pending_single_choice_and_unchanged_avoid_invocation(self):
        original = source()
        cases = []
        closed = copy.deepcopy(original); closed["task"]["state"] = "closed"; cases.append(closed)
        pending = copy.deepcopy(original); pending["batches"][0]["status"] = "pending"; cases.append(pending)
        one = copy.deepcopy(original); one["libraries"][2]["available_for_analysis"] = False; cases.append(one)
        won = copy.deepcopy(original)
        won["batches"] = [batch(won["task"], won["libraries"][0], 1, [row("winner", .8, .8)])]
        cases.append(won)
        for s in cases:
            with self.subTest(state=s["task"]["state"]):
                self.assertIsNone(prepare(s)["request"])
        previous = prepare(original)
        unchanged = prepare(original, previous_input_digest=previous["input_digest"])
        self.assertEqual(unchanged["reason"], "unchanged_input_reuse_host_advice")
        self.assertIsNone(unchanged["request"])

    def test_missing_or_stale_chemical_notes_block_before_model(self):
        for area, key in (("pair_notes", "ARTIFICIAL_ID_g1"), ("library_notes", "LIBRARY_C")):
            s = source(); s["chemistry"][area].pop(key)
            self.assertEqual(prepare(s)["status"], "need_information")
            self.assertIsNone(prepare(s)["request"])
        s = source(); s["chemistry"]["pair_notes"]["ARTIFICIAL_ID_g1"]["row_sha256"] = "stale"
        self.assertEqual(prepare(s)["status"], "need_information")

    def test_advice_can_agree_with_or_deviate_from_baseline_without_claiming_science(self):
        s = source(); a = prepare(s)
        for lid in ("LIBRARY_C", "LIBRARY_D"):
            receipt = accept(a, canned_answer(a["input_digest"], lid), s)
            self.assertEqual(receipt["library_id"], lid)
            self.assertEqual(receipt["execution"], "not_performed")
            self.assertEqual(receipt["scientific_validity"], "not_assessed")

    def test_changed_source_or_tampered_menu_cannot_authorize_old_advice(self):
        s = source(); a = prepare(s); answer = canned_answer(a["input_digest"])
        changed = copy.deepcopy(s); changed["resource_summary"]["internal_compute"] = "new report"
        with self.assertRaises(ContractError): accept(a, answer, changed)
        altered = copy.deepcopy(a); altered["packet"]["eligible_library_ids"].append("LIBRARY_A")
        with self.assertRaises(ContractError): accept(altered, answer, s)

    def test_unknown_citations_tried_assets_extra_fields_and_success_claims_rejected(self):
        s = source(); a = prepare(s); answer = canned_answer(a["input_digest"])
        mutations = ({"supporting_ids": ["invented"]}, {"library_id": "LIBRARY_A"},
                     {"scientific_claim": "measured_success"}, {"submit_payload": {}},
                     {"disposition": []}, {"input_digest": "stale"})
        for mutation in mutations:
            bad = {**answer, **mutation}
            with self.subTest(mutation=mutation), self.assertRaises(ContractError): accept(a, bad, s)

    def test_abstention_requests_information_without_an_executable_action(self):
        s = source(); a = prepare(s); answer = canned_answer(a["input_digest"])
        answer.update(disposition="need_information", library_id=None,
                      hypothesis="Need a reviewed site mapping to distinguish the interpretations.",
                      information_requests=["Reviewed original-parent/site mapping"],
                      supporting_ids=[], counterexample_ids=[])
        self.assertEqual(accept(a, answer, s)["disposition"], "need_information")

    def test_large_context_is_blocked_without_selective_evidence_omission(self):
        s = source(); before = copy.deepcopy(s)
        a = prepare(s, max_context_chars=100)
        self.assertEqual(a["reason"], "context_too_large_no_evidence_dropped")
        self.assertIsNone(a["request"])
        self.assertEqual(s, before)

    def test_json_wrappers_duplicates_and_nonfinite_values_rejected(self):
        for text in ('{"x":1,"x":2}', '```json\n{}\n```', '{"x":NaN}', '[]'):
            with self.subTest(text=text), self.assertRaises(ContractError): parse_answer(text)

    def test_poor_but_complete_results_can_still_receive_scientific_review(self):
        s = source()
        for b in s["batches"]:
            for r in b["rows"]:
                r["values"]["similarity"] = .2
                s["chemistry"]["pair_notes"][r["chemical_id"]]["row_sha256"] = digest(r)
        a = prepare(s)
        self.assertEqual(a["baseline"]["reason"], "no_hard_feasible_matched_output_observed")
        self.assertEqual(a["status"], "invoke")
        self.assertEqual(a["packet"]["batches"], s["batches"])


if __name__ == "__main__":
    unittest.main()
