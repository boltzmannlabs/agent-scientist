"""Artifact/endpoint contract tests with artificial records; no scientific calls."""

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from evaluation_support import confirmed_panel_summary, verified_packet_file
from feedback_policy import InputError


class EvaluationSupportTests(unittest.TestCase):
    def test_json_and_csv_manifests_verify_without_weakening_tamper_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.csv'
            path.write_bytes(b'x\n1\n')
            entry = {'relative_path': 'data.csv', 'bytes': 4,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for size in [4, '4']:
                self.assertEqual(verified_packet_file(tmp, 'data.csv', [{**entry, 'bytes': size}]), b'x\n1\n')
            path.write_bytes(b'x\n2\n')
            with self.assertRaises(InputError):
                verified_packet_file(tmp, 'data.csv', [entry])

    def test_invalid_byte_types_duplicate_members_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'a').write_bytes(b'x')
            entry = {'relative_path': 'a', 'bytes': 1, 'sha256': hashlib.sha256(b'x').hexdigest()}
            for size in [True, 1.0, -1, '-1', None]:
                with self.subTest(size=size), self.assertRaises(InputError):
                    verified_packet_file(tmp, 'a', [{**entry, 'bytes': size}])
            with self.assertRaises(InputError):
                verified_packet_file(tmp, 'a', [entry, entry])
            with self.assertRaises(InputError):
                verified_packet_file(tmp, '../a', [{**entry, 'relative_path': '../a'}])

    def panel(self):
        ids = ['ARTIFICIAL_%s' % i for i in range(10)]
        rows = [{'identity': i, 'role': 'generated', 'status': 'SUCCESS', 'score': -10 + n,
                 'joint_eligible': True, 'pose_verified': True} for n, i in enumerate(ids)]
        return ids, rows

    def test_complete_panel_has_ten_eligible_scores(self):
        ids, rows = self.panel()
        summary = confirmed_panel_summary(ids, rows)
        self.assertEqual(summary['confirmed_eligible_final_slots'], 10)
        self.assertEqual(summary['mean_native_vina'], -5.5)
        self.assertTrue(summary['all_eligible'])

    def test_ten_successful_scores_with_one_ineligible_or_unknown_has_no_primary_mean(self):
        ids, rows = self.panel()
        for eligible in [False, None, 'True']:
            changed = copy.deepcopy(rows)
            changed[0]['joint_eligible'] = eligible
            summary = confirmed_panel_summary(ids, changed)
            self.assertEqual(summary['successful_pose_score_slots'], 10)
            self.assertEqual(summary['confirmed_eligible_final_slots'], 9)
            self.assertIsNone(summary['mean_native_vina'])
            self.assertEqual(summary['status'], 'INCOMPLETE_EVALUATION')

    def test_missing_slot_cannot_be_replaced_with_an_extra_better_result(self):
        ids, rows = self.panel()
        extra = {**rows[0], 'identity': 'UNCOMMITTED_EXTRA', 'score': -100}
        summary = confirmed_panel_summary(ids, rows[1:] + [extra])
        self.assertEqual(summary['confirmed_eligible_final_slots'], 9)
        self.assertIsNone(summary['mean_native_vina'])
        self.assertIsNone(confirmed_panel_summary(ids[:9] + [None], rows)['mean_native_vina'])

    def test_invalid_pose_failure_reference_and_nonfinite_score_cannot_fill_slot(self):
        ids, rows = self.panel()
        for change in [{'pose_verified': False}, {'status': 'FAILED'}, {'role': 'control'},
                       {'score': float('nan')}, {'score': float('inf')}, {'score': True}]:
            changed = copy.deepcopy(rows)
            changed[0].update(change)
            with self.subTest(change=change):
                summary = confirmed_panel_summary(ids, changed)
                self.assertEqual(summary['confirmed_eligible_final_slots'], 9)
                self.assertIsNone(summary['mean_native_vina'])

    def test_duplicate_commitment_or_duplicate_result_is_ambiguous(self):
        ids, rows = self.panel()
        with self.assertRaises(InputError):
            confirmed_panel_summary([ids[0]] * 10, rows)
        with self.assertRaises(InputError):
            confirmed_panel_summary(ids, rows + [rows[0]])


if __name__ == '__main__':
    unittest.main()
