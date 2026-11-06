"""Main-baseline contract checks; no SDK import, model call or scientific job."""
from copy import deepcopy
import json
import unittest
from jsonschema import ValidationError

from workflow.baseline_episode import prepare_packet, validate_main_result
from workflow.identifiers import digest, present_assignment, restore_assignment
from workflow.test_identifiers import assignment as identifier_fixture


def assignment():
    value = identifier_fixture()
    value.update(schema_version=1, campaign_id='engineering-campaign',
                 evidence_snapshot_digest='c' * 64, objective_config_digest='d' * 64, limitations=[])
    for lib in value['library_options']:
        lib['local_path'] = '/engineering-fixture/library.csv'
    value['input_digest'] = digest({k: v for k, v in value.items() if k != 'input_digest'})
    return value


def wire_answer(packet, status='action_requested'):
    wire = packet['assignment']
    action = wire['helper_summaries']['eligible_actions'][0]
    return {'schema_version': 1, 'assignment_id': wire['assignment_id'], 'episode_id': wire['episode_id'],
            'input_digest': wire['input_digest'], 'status': status,
            'chosen_action': {'kind': 'generate', 'parent_id': action['parent_candidate_id'],
                              'library_id': action['library_id'], 'action_key': action['action_key']},
            'evidence_ids': wire['helper_summaries']['rows'][0]['evidence_ids'],
            'final_candidate_ids': [], 'pending_jobs': [], 'artifact_refs': [],
            'rationale': 'ENGINEERING FIXTURE: compare the provided eligible action.',
            'stop_reason': 'host_execution_requested' if status == 'action_requested' else 'missing_dependency',
            'limitations': ['No inference or scientific execution in this fixture.'], 'information_requests': []}


class BaselineEpisodeTests(unittest.TestCase):
    def test_same_canonical_assignment_renderer_and_scientific_values(self):
        original = assignment()
        before = deepcopy(original)
        packet, manifest, schema, text = prepare_packet(original)
        expected_wire, expected_manifest = present_assignment(original)
        self.assertEqual(packet['assignment'], expected_wire)
        self.assertEqual(manifest, expected_manifest)
        self.assertEqual(restore_assignment(packet['assignment'], manifest), original)
        self.assertEqual(original, before)
        self.assertEqual(json.loads(text), packet)
        self.assertEqual(packet['assignment']['helper_summaries']['rows'][0]['values'],
                         original['helper_summaries']['rows'][0]['values'])
        self.assertIn('action_requested', schema['properties']['status']['enum'])

    def test_wire_action_returns_checked_canonical_request_not_job_or_success(self):
        original = assignment()
        packet, _, _, _ = prepare_packet(original)
        result = validate_main_result(original, {'completed': True, 'api_calls': 1,
                                                'final_response': json.dumps(wire_answer(packet))})
        self.assertEqual(result['validation_status'], 'passed')
        self.assertEqual(result['outcome']['status'], 'action_requested')
        self.assertEqual(result['outcome']['input_digest'], original['input_digest'])
        self.assertEqual(result['outcome']['chosen_action']['action_key'], 'a' * 64)
        self.assertEqual(result['outcome']['chosen_action']['parent_id'], original['parent_options'][0]['candidate_id'])
        self.assertEqual(result['outcome']['pending_jobs'], [])
        self.assertEqual(result['outcome']['final_candidate_ids'], [])

    def test_blocked_proposal_is_never_promoted_to_executable_request(self):
        original = assignment()
        packet, _, _, _ = prepare_packet(original)
        native = {'completed': True, 'final_response': json.dumps(wire_answer(packet, 'blocked'))}
        result = validate_main_result(original, native)
        self.assertEqual(result['outcome']['status'], 'blocked')
        self.assertEqual(result['outcome']['chosen_action']['kind'], 'generate')

    def test_incomplete_or_truncated_native_execution_is_rejected(self):
        original = assignment()
        packet, _, _, _ = prepare_packet(original)
        valid = {'completed': True, 'final_response': json.dumps(wire_answer(packet))}
        for change in ({'completed': False}, {'truncated': True}, {'failed': True}, {'error': 'provider error'}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_main_result(original, {**valid, **change})

    def test_invented_evidence_action_or_job_and_duplicate_json_fail(self):
        original = assignment()
        packet, _, _, _ = prepare_packet(original)
        correct = wire_answer(packet)
        variants = []
        wrong = deepcopy(correct); wrong['evidence_ids'] = ['invented']; variants.append(wrong)
        wrong = deepcopy(correct); wrong['chosen_action']['action_key'] = 'A999'; variants.append(wrong)
        wrong = deepcopy(correct); wrong['pending_jobs'] = [{'job_name': 'Fragment_Based_Optimization', 'doc_id': 'invented', 'status': 'pending'}]; variants.append(wrong)
        for answer in variants:
            with self.assertRaises((ValueError, ValidationError)):
                validate_main_result(original, {'completed': True, 'final_response': json.dumps(answer)})
        with self.assertRaises(ValueError):
            validate_main_result(original, {'completed': True, 'final_response': '{"status":"blocked","status":"completed"}'})

    def test_wrong_runtime_mode_and_changed_canonical_state_are_rejected(self):
        original = assignment()
        wrong = deepcopy(original); wrong['capability_contract']['execution_mode'] = 'planning_only'
        wrong['input_digest'] = digest({k: v for k, v in wrong.items() if k != 'input_digest'})
        with self.assertRaises(ValueError):
            prepare_packet(wrong)
        wrong = deepcopy(original); wrong['task']['question'] = 'Changed after freezing'
        with self.assertRaises(ValueError):
            prepare_packet(wrong)
        wrong = deepcopy(original); wrong['input_digest'] = 'f' * 64
        with self.assertRaises(ValueError):
            prepare_packet(wrong)


if __name__ == '__main__':
    unittest.main()
