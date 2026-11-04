import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pilot.bridge import AdapterError, JOB_NAME, NodeAPIAdapter, ReceiptError


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "library.csv"
        self.path.write_text("SMILES\nCCO\n")
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.request = {"request_id": "FIXTURE_COMMON_REQUEST", "library_csv_path": str(self.path),
                        "library_content_sha256": self.sha, "reference": {"representation": "CCN"},
                        "generation_parameters": {"global_models": [{"name": "FIXTURE_PROPERTY", "min_threshold": "-4.00", "max_threshold": "0.40"}]}}

    def test_existing_tool_names_payload_receipts_and_read_only_monitoring(self):
        calls = []
        def callback(name, args):
            calls.append((name, args))
            return json.dumps({
                "boltzmann_upload": {"status": "uploaded", "s3_path": "users/FIXTURE/library.csv", "sha256": self.sha},
                "boltzmann_submit": {"status": "accepted", "doc_id": "FIXTURE_DOC", "job_name": JOB_NAME},
                "boltzmann_status": {"error": "FIXTURE transport observation error", "status": "unknown"},
                "boltzmann_download": {"status": "downloaded"}}[name])
        adapter = NodeAPIAdapter(callback)
        uploaded = adapter.upload(self.request)
        submitted = adapter.submit(self.request, uploaded)
        self.assertEqual(calls[0][0], "boltzmann_upload")
        self.assertEqual(calls[0][1]["input_field"], "library_path")
        self.assertEqual(calls[0][1]["experiment_data"], {"ref_mol": "CCN", **self.request["generation_parameters"]})
        self.assertFalse(calls[0][1]["allow_partial_validation"])
        self.assertEqual(calls[1][1]["experiment_data"]["library_path"], uploaded["s3_path"])
        self.assertFalse(calls[1][1]["allow_partial_validation"])
        self.path.unlink()  # Monitoring must not need the original upload file.
        observed = adapter.status(self.request, submitted)
        self.assertEqual(observed["status"], "unknown")
        self.assertEqual(submitted["status"], "accepted")
        self.assertEqual(calls[-1][1], {"job_name": JOB_NAME, "doc_id": "FIXTURE_DOC"})
        adapter.download("https://fixture.invalid/result?signature=FIXTURE", self.temporary.name)
        self.assertEqual(calls[-1][0], "boltzmann_download")

    def test_changed_assets_payload_overrides_and_mismatched_receipts_reject_before_call(self):
        calls = []
        def callback(name, args):
            calls.append(name)
            return {"status": "uploaded", "s3_path": "users/FIXTURE/library.csv", "sha256": self.sha}
        adapter = NodeAPIAdapter(callback)
        uploaded = adapter.upload(self.request)
        count = len(calls)
        changed = copy.deepcopy(self.request); changed["request_id"] = "OTHER_REQUEST"
        with self.assertRaises(AdapterError): adapter.submit(changed, uploaded)
        changed = copy.deepcopy(self.request); changed["generation_parameters"]["ref_mol"] = "CCC"
        with self.assertRaises(AdapterError): adapter.upload(changed)
        self.path.write_text("SMILES\nCCC\n")
        with self.assertRaises(AdapterError): adapter.upload(self.request)
        self.assertEqual(len(calls), count)

    def test_explicit_partial_validation_option_is_forwarded_without_changing_scientific_inputs(self):
        calls = []
        def callback(name, args):
            calls.append((name, args))
            if name == "boltzmann_upload":
                return {"status": "uploaded", "s3_path": "users/FIXTURE/library.csv", "sha256": self.sha}
            return {"status": "accepted", "doc_id": "FIXTURE_DOC", "job_name": JOB_NAME}
        for value in ("true", 1, None):
            with self.assertRaises(AdapterError): NodeAPIAdapter(callback, allow_partial_validation=value)
        # This is a fixture for forwarding an approval already obtained by the
        # host. It does not grant or manufacture actual user approval.
        adapter = NodeAPIAdapter(callback, allow_partial_validation=True)
        uploaded = adapter.upload(self.request)
        adapter.submit(self.request, uploaded)
        self.assertTrue(all(args["allow_partial_validation"] is True for _, args in calls))
        self.assertEqual(calls[0][1]["experiment_data"], {"ref_mol": "CCN", **self.request["generation_parameters"]})
        self.path.write_text("SMILES\nCCC\n")
        with self.assertRaises(AdapterError): adapter.upload(self.request)
        self.assertEqual(len(calls), 2)

    def test_dispatch_ambiguity_native_blocks_and_bad_receipts_are_not_retried(self):
        calls = []
        def timeout(name, args):
            calls.append(name)
            raise TimeoutError("FIXTURE callback outcome unknown")
        with self.assertRaises(TimeoutError): NodeAPIAdapter(timeout).upload(self.request)
        self.assertEqual(calls, ["boltzmann_upload"])
        blocked = {"error": "FIXTURE validation warning", "status": "approval_required", "approval_required": True}
        result = NodeAPIAdapter(lambda *_: blocked).upload(self.request)
        self.assertTrue(result["approval_required"])
        with self.assertRaises(AdapterError): NodeAPIAdapter(lambda *_: {}).submit(self.request, result)
        for response in ("not json", {}, {"value": float("nan")},
                         {"status": "uploaded", "s3_path": "users/FIXTURE/library.csv", "sha256": "wrong"}):
            with self.subTest(response=response), self.assertRaises(ReceiptError):
                NodeAPIAdapter(lambda *_, response=response: response).upload(self.request)

    def test_missing_property_objective_blocks_before_upload_but_old_job_monitoring_remains_possible(self):
        from pilot.bridge import BINDING, _request
        calls = []
        adapter = NodeAPIAdapter(lambda name, args: calls.append((name, args)) or {"status": "running"})
        original = copy.deepcopy(self.request)
        for parameters in ({}, {"global_models": []}, {"global_models": [], "custom_models": []},
                           {"attribute": []}, {"global_models": [{"name": ""}]},
                           {"custom_models": [{"id": "FIXTURE_MODEL"}]}):
            request = copy.deepcopy(original); request["generation_parameters"] = parameters
            with self.subTest(parameters=parameters), self.assertRaises(AdapterError):
                adapter.upload(request)
        self.assertEqual(calls, [])
        # An old accepted request without a selection must still be monitorable.
        old = copy.deepcopy(original); old["generation_parameters"] = {}
        _, binding = _request(old, verify_file=False)
        observed = adapter.status(old, {BINDING: binding, "doc_id": "FIXTURE_OLD_JOB", "job_name": JOB_NAME})
        self.assertEqual(observed["status"], "running")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
