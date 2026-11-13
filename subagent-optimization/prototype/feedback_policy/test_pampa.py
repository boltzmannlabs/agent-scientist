"""Artificial PAMPA policy records; no predictor or platform access."""
from copy import deepcopy
import unittest

from feedback_policy import InputError, decide, select_panel
from fixtures import action, candidate, config, panel_rows, snapshot


def pampa_config():
    value = config()
    value["property_metric"] = "pampa"
    del value["constraints"]["solubility"]
    value["constraints"]["pampa"] = {"min": .5, "max": 1,
                                    "method": "FIXTURE_PAMPA_PROBABILITY", "unit": "dimensionless"}
    value["objective_models"] = {"global_models": [
        {"name": "PAMPA", "min_threshold": .5, "max_threshold": 1}]}
    value["route_objective_models"] = {"graph_ga": {"global_models": [
        {"name": "PAMPA", "min_threshold": 0, "max_threshold": .5}]}}
    return value


def pampa_row(identity="FIXTURE_LEAD", *, score=.8, role="lead", vina=-8):
    row = candidate(identity, role=role, vina=vina)
    row["measurements"].pop("solubility")
    row["measurements"]["pampa"] = {"value": score, "status": "ok" if score is not None else "unavailable",
                                    "method": "FIXTURE_PAMPA_PROBABILITY", "unit": "dimensionless"}
    return row


def pampa_action(route):
    card = action(route)
    config = pampa_config()
    models = config["route_objective_models"].get(route, config["objective_models"])
    card["payload"].update(deepcopy(models))
    if route == "graph_ga":
        card["targets"] = ["pampa"]
    return card


class PampaPolicy(unittest.TestCase):
    def setUp(self):
        self.config = pampa_config()
        self.cards = [pampa_action("crem"), pampa_action("graph_ga")]

    def test_measured_pampa_deficit_can_change_the_route(self):
        state = snapshot([pampa_row(), pampa_row("NEW", role="generated", score=.2)])
        decision = decide(state, self.cards, self.config)
        self.assertEqual(decision["reason"], "measured_pampa_deficit")
        self.assertEqual(decision["chosen"]["route"], "graph_ga")
        self.assertEqual(decision["observations"]["pampa_only_failures"], ["NEW"])

    def test_missing_or_out_of_domain_probability_is_unknown_not_a_deficit(self):
        for score in (None, -.1, 1.1):
            state = snapshot([pampa_row(), pampa_row("NEW", role="generated", score=score)])
            decision = decide(state, self.cards, self.config)
            self.assertEqual(decision["chosen"]["route"], "crem")
            self.assertEqual(decision["observations"]["pampa_only_failures"], [])
            self.assertIn("NEW", decision["observations"]["unresolved_identities"])

    def test_feasible_lead_does_not_invent_a_pampa_deficit(self):
        decision = decide(snapshot([pampa_row()]), self.cards, self.config)
        self.assertEqual(decision["chosen"]["route"], "crem")

    def test_shared_panel_uses_pampa_and_retains_missing_slots(self):
        rows = [pampa_row("PASS", score=.5, role="generated", vina=-8),
                pampa_row("FAIL", score=.49, role="generated", vina=-20),
                pampa_row("UNKNOWN", score=None, role="generated", vina=-30)]
        panel = select_panel(rows, self.config)
        self.assertEqual(panel["identities"], ["PASS"] + [None] * 9)

    def test_old_solubility_cards_do_not_satisfy_pampa_objective_configuration(self):
        decision = decide(snapshot([pampa_row()]), [action("crem")], self.config)
        self.assertIsNone(decision["chosen"])
        self.assertEqual(decision["rejected"][0]["reason"], "objective_selection_mismatch")

    def test_irrelevant_solubility_values_cannot_change_pampa_eligibility(self):
        row = pampa_row("NEW", role="generated")
        before = select_panel([row], self.config)
        row["measurements"]["solubility"] = {"value": -99999, "status": "ok", "method": "UNKNOWN", "unit": "UNKNOWN"}
        self.assertEqual(before, select_panel([row], self.config))

    def test_ga_reward_and_crem_request_use_separate_frozen_bounds(self):
        state = snapshot([pampa_row(), pampa_row("NEW", role="generated", score=.2)])
        decision = decide(state, self.cards, self.config)
        self.assertEqual(decision["rejected"], [])
        self.assertEqual(decision["chosen"]["payload"]["global_models"][0]["max_threshold"], .5)
        self.assertEqual(self.cards[0]["payload"]["global_models"][0]["max_threshold"], 1)

    def test_ga_cannot_silently_use_one_as_its_positive_class_reward_boundary(self):
        self.config["route_objective_models"]["graph_ga"] = deepcopy(self.config["objective_models"])
        with self.assertRaises(InputError):
            decide(snapshot([pampa_row()]), self.cards, self.config)


class PampaLabels(unittest.TestCase):
    def setUp(self):
        self.config = pampa_config()
        self.config["pampa_output_kind"] = "class_label"
        self.config["pampa_score_boundary"] = .5
        self.config["constraints"]["pampa"].update(min=1, max=1, method="FIXTURE_PAMPA_LABEL")
        self.cards = [pampa_action("crem"), pampa_action("graph_ga")]

    def row(self, identity="FIXTURE_LEAD", *, label=1, role="lead"):
        row = pampa_row(identity, role=role, score=label)
        row["measurements"]["pampa"].update(method="FIXTURE_PAMPA_LABEL", output_kind="class_label")
        return row

    def test_positive_labels_keep_docking_focus_without_inventing_probability(self):
        row = self.row(label=1.0)
        decision = decide(snapshot([row]), self.cards, self.config)
        self.assertEqual(decision["chosen"]["route"], "crem")
        self.assertEqual(decision["observations"]["pampa_only_failures"], [])
        self.assertEqual(row["measurements"]["pampa"]["output_kind"], "class_label")

    def test_negative_native_class_can_be_a_measured_eligibility_gap(self):
        decision = decide(snapshot([self.row(), self.row("NEW", label=0, role="generated")]),
                          self.cards, self.config)
        self.assertEqual(decision["reason"], "measured_pampa_deficit")
        self.assertEqual(decision["chosen"]["payload"]["global_models"][0]["max_threshold"], .5)

    def test_intermediate_value_or_wrong_output_kind_is_unresolved(self):
        for score, kind in ((.8, "class_label"), (1, "class_score")):
            row = self.row("NEW", label=score, role="generated")
            row["measurements"]["pampa"]["output_kind"] = kind
            decision = decide(snapshot([self.row(), row]), self.cards, self.config)
            self.assertIn("NEW", decision["observations"]["unresolved_identities"])
            self.assertEqual(decision["observations"]["pampa_only_failures"], [])

    def test_common_label_panel_uses_class_one_without_scalar_confidence_ranking(self):
        rows = [self.row("POSITIVE", role="generated"), self.row("NEGATIVE", label=0, role="generated")]
        panel = select_panel(rows, self.config)
        self.assertEqual(panel["identities"], ["POSITIVE"] + [None] * 9)

    def test_label_mode_does_not_move_ga_probability_boundary_to_one(self):
        self.config["route_objective_models"]["graph_ga"]["global_models"][0]["max_threshold"] = 1
        with self.assertRaises(InputError):
            decide(snapshot([self.row()]), self.cards, self.config)


if __name__ == "__main__":
    unittest.main()
