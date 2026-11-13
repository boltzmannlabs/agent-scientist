"""Adapter tests use artificial identities and measurements; no chemistry/jobs."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from feedback_policy import InputError
from observations import (csv_records, import_basic_vina_csv, import_long_records,
                          prepare_basic_vina_csv, sha256, verified_file)
from replay_archive import import_p38_archive


REGISTRY_FIELDS = ["candidate_id", "canonical_identity", "status", "hosted_values_json"]
METRIC_FIELDS = ["case_id", "run_id", "candidate_id", "canonical_identity", "phase",
                 "metric_id", "value", "unit", "status", "method_version"]
CONTEXT = {"case_id": "FIXTURE_CASE", "run_id": "FIXTURE_RUN"}


def as_csv(fields, rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def metric(**changes):
    return {**CONTEXT, "candidate_id": "A", "canonical_identity": "CC", "phase": "search",
            "metric_id": "qed", "value": ".81234567", "unit": "dimensionless",
            "status": "SUCCESS", "method_version": "FIXTURE_RDKIT", **changes}


def bindings():
    return [{"source_metric": "qed", "target_metric": "qed", "producer_method": "FIXTURE_RDKIT",
             "unit": "dimensionless", "qualified": True},
            {"source_metric": "smina_raw", "target_metric": "smina_raw", "producer_method": "Smina fixture",
             "unit": "native Smina", "qualified": True}]


def registry():
    return [{"candidate_id": "A", "canonical_identity": "CC", "status": "VALID_CONNECTED_COMPLETE",
             "hosted_values_json": '{"QED":"0.81"}'}]


class ObservationImport(unittest.TestCase):
    def imported(self, rows, *, mapping=None, candidates=None):
        return import_long_records(as_csv(REGISTRY_FIELDS, registry() if candidates is None else candidates),
                                   as_csv(METRIC_FIELDS, rows), expected_context=CONTEXT,
                                   bindings=bindings() if mapping is None else mapping)

    def test_precise_record_and_phases_preserved_without_using_rounded_hosted_value(self):
        rows = [metric(), metric(phase="final", value=".83333333"),
                metric(metric_id="smina_raw", value="-8.1", method_version="Smina fixture", unit="native Smina")]
        imported = self.imported(rows)
        self.assertEqual(len(imported["observations"]), 3)
        self.assertEqual(imported["phase_candidates"]["search"][0]["measurements"]["qed"]["value"], .81234567)
        self.assertEqual(imported["phase_candidates"]["final"][0]["measurements"]["qed"]["value"], .83333333)
        self.assertEqual(imported["registry"][0]["hosted_values_json"], registry()[0]["hosted_values_json"])
        measurements = imported["phase_candidates"]["search"][0]["measurements"]
        self.assertEqual(measurements["smina_raw"]["value"], -8.1)
        for absent in ("solubility", "vina"):
            self.assertIsNone(measurements[absent]["value"])
            self.assertEqual(measurements[absent]["status"], "unavailable")

    def test_smina_diffdock_and_hosted_lipophilicity_cannot_be_relabelled(self):
        for source, producer, target in (("smina_raw", "Smina fixture", "vina"),
                                          ("confidence", "DiffDock fixture", "vina"),
                                          ("Lipophilicity", "hosted", "crippen_logp")):
            mapping = [{"source_metric": source, "target_metric": target, "producer_method": producer,
                        "unit": "dimensionless", "qualified": True}]
            with self.subTest(source=source), self.assertRaises(InputError):
                self.imported([metric()], mapping=mapping)

    def test_failed_nonnumeric_and_nonfinite_values_remain_unresolved(self):
        for row in (metric(value=""), metric(value="nan"), metric(value="inf"), metric(value="not-a-number"),
                    metric(value="100", status="FAILED")):
            imported = self.imported([row])
            value = imported["phase_candidates"]["search"][0]["measurements"]["qed"]
            self.assertIsNone(value["value"])
            self.assertNotEqual(value["status"], "ok")
            self.assertEqual(imported["observations"][0]["source"]["value"], row["value"])

    def test_wrong_method_unit_or_host_qualification_is_not_a_valid_measurement(self):
        for row in (metric(method_version="OTHER"), metric(unit="mg/mL")):
            value = self.imported([row])["phase_candidates"]["search"][0]["measurements"]["qed"]
            self.assertEqual(value["status"], "unqualified")
        mapping = bindings()
        mapping[0]["qualified"] = False
        value = self.imported([metric()], mapping=mapping)["phase_candidates"]["search"][0]["measurements"]["qed"]
        self.assertEqual(value["status"], "unqualified")

    def test_pampa_labels_require_explicit_kind_and_do_not_merge_with_scores(self):
        binding = {"source_metric": "PAMPA", "target_metric": "pampa", "producer_method": "FIXTURE_RDKIT",
                   "unit": "dimensionless", "qualified": True, "output_kind": "class_label"}
        row = metric(metric_id="PAMPA", value="1.0")
        imported = self.imported([row], mapping=[binding])
        value = imported["phase_candidates"]["search"][0]["measurements"]["pampa"]
        self.assertEqual((value["value"], value["output_kind"]), (1.0, "class_label"))
        missing = deepcopy(binding)
        missing.pop("output_kind")
        with self.assertRaises(InputError):
            self.imported([row], mapping=[missing])
        invalid = self.imported([metric(metric_id="PAMPA", value=".7")], mapping=[binding])
        self.assertEqual(invalid["phase_candidates"]["search"][0]["measurements"]["pampa"]["status"], "unavailable")
        score_binding = {**binding, "source_metric": "PAMPA_prob", "output_kind": "class_score"}
        conflicted = self.imported([row, metric(metric_id="PAMPA_prob", value="1.0")], mapping=[binding, score_binding])
        self.assertEqual(conflicted["phase_candidates"]["search"][0]["measurements"]["pampa"]["status"], "conflict")

    def test_identity_context_and_unknown_transport_keys_are_rejected(self):
        for row in (metric(canonical_identity="CCC"), metric(candidate_id="UNKNOWN"),
                    metric(run_id="OTHER_RUN"), metric(case_id="OTHER_CASE")):
            with self.subTest(row=row), self.assertRaises(InputError):
                self.imported([row])

    def test_conflicts_are_explicit_and_identical_duplicates_do_not_count_twice(self):
        imported = self.imported([metric(), metric(value=".9")])
        self.assertEqual(len(imported["conflicts"]), 1)
        self.assertEqual(imported["phase_candidates"]["search"][0]["measurements"]["qed"]["status"], "conflict")
        imported = self.imported([metric(), metric()])
        self.assertEqual(imported["conflicts"], [])
        self.assertEqual(len(imported["duplicate_measurement_keys"]), 1)
        self.assertEqual(len(imported["phase_candidates"]["search"]), 1)
        self.assertEqual(len(imported["observations"]), 2)

    def test_row_order_does_not_change_projection_and_unmapped_records_are_retained(self):
        rows = [metric(), metric(metric_id="unknown_metric", value="4.2")]
        forward, reverse = self.imported(rows), self.imported(list(reversed(rows)))
        self.assertEqual(forward["phase_candidates"], reverse["phase_candidates"])
        self.assertEqual(forward["unmapped_metric_counts"], {"unknown_metric": 1})
        self.assertEqual(len(forward["observations"]), 2)

    def test_ambiguous_registry_and_malformed_csv_rejected(self):
        with self.assertRaises(InputError):
            self.imported([metric()], candidates=registry() * 2)
        for raw in (b"a,a\n1,2\n", b"a,b\n1\n", b"a,b\n1,2,3\n"):
            with self.subTest(raw=raw), self.assertRaises(InputError):
                csv_records(raw, {"a"})

    def test_manifest_verification_detects_tampering_and_blocks_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            root.mkdir()
            (root / "record.csv").write_bytes(b"a\n1\n")
            manifest = [{"relative_path": "record.csv", "bytes": "4", "sha256": sha256(b"a\n1\n")}]
            self.assertEqual(verified_file(root, "record.csv", manifest), b"a\n1\n")
            (root / "record.csv").write_bytes(b"a\n2\n")
            with self.assertRaises(InputError):
                verified_file(root, "record.csv", manifest)
            (Path(directory) / "outside.csv").write_bytes(b"a\n1\n")
            (root / "escape.csv").symlink_to(Path(directory) / "outside.csv")
            for name in ("../outside.csv", "escape.csv"):
                with self.subTest(name=name), self.assertRaises(InputError):
                    verified_file(root, name, manifest)


class BasicVinaImport(unittest.TestCase):
    def setUp(self):
        self.inputs = [{"candidate_id": "A", "canonical_identity": "CC", "SMILES": "CC", "NAMES": "mol-a"},
                       {"candidate_id": "B", "canonical_identity": "CCC", "SMILES": "CCC", "NAMES": "mol-b"}]

    def native(self, rows, *, qualified=False, verified=(), selected=0):
        raw = as_csv(["SMILES", "NAMES", "Ligand_no", "Pose", "Score"], rows)
        return import_basic_vina_csv(raw, self.inputs, context={**CONTEXT, "phase": "search"},
                                     method="Vina fixture", unit="kcal/mol", selected_pose_index=selected,
                                     qualified=qualified, verified_pose_keys=verified)

    def row(self, ordinal=1, pose=0, score=-8):
        entry = self.inputs[ordinal - 1]
        return {"SMILES": entry["SMILES"], "NAMES": entry["NAMES"],
                "Ligand_no": str(ordinal), "Pose": str(pose), "Score": str(score)}

    def test_failure_sentinel_is_null_despite_finite_score_and_mixed_batch_success(self):
        result = self.native([self.row(), self.row(2, -1, 100)], qualified=True, verified={(1, 0)})
        good, failed = result["selected_measurements"]
        self.assertEqual(good["status"], "SUCCESS")
        self.assertEqual((failed["status"], failed["value"]), ("FAILED", ""))
        self.assertEqual(result["pose_records"][1]["source"]["Score"], "100")

    def test_pose_correspondence_and_explicit_selection_preserve_all_poses(self):
        result = self.native([self.row(pose=1, score=-9), self.row(pose=0, score=-8)],
                             qualified=True, verified={(1, 0), (1, 1)})
        self.assertEqual(len(result["pose_records"]), 2)
        selected = result["selected_measurements"][0]
        self.assertEqual((selected["value"], selected["csv_pose_index"], selected["sdf_pose_number"]), ("-8", 0, 1))
        self.assertEqual(result["selected_measurements"][1]["status"], "UNAVAILABLE")

    def test_source_definition_alone_does_not_qualify_native_measurement(self):
        for qualified, verified in ((False, {(1, 0)}), (True, ())):
            result = self.native([self.row()], qualified=qualified, verified=verified)
            self.assertEqual(result["selected_measurements"][0]["status"], "UNQUALIFIED")

    def test_native_unqualified_and_failed_statuses_survive_long_record_projection(self):
        native = self.native([self.row(), self.row(2, -1, 100)])
        rows = [{k: record[k] for k in METRIC_FIELDS} for record in native["selected_measurements"]]
        candidates = [{"candidate_id": r["candidate_id"], "canonical_identity": r["canonical_identity"],
                       "status": "VALID_CONNECTED_COMPLETE", "hosted_values_json": "{}"} for r in self.inputs]
        imported = import_long_records(as_csv(REGISTRY_FIELDS, candidates), as_csv(METRIC_FIELDS, rows),
                                       expected_context=CONTEXT, bindings=[{
                                           "source_metric": "vina", "target_metric": "vina",
                                           "producer_method": "Vina fixture", "unit": "kcal/mol", "qualified": True}])
        statuses = {row["identity"]: row["measurements"]["vina"]["status"]
                    for row in imported["phase_candidates"]["search"]}
        self.assertEqual(statuses, {"CC": "unqualified", "CCC": "failed"})

    def test_output_row_order_not_used_as_identity_and_bad_names_rejected(self):
        rows = [self.row(2), self.row(1)]
        result = self.native(rows, qualified=True, verified={(1, 0), (2, 0)})
        self.assertEqual([r["candidate_id"] for r in result["selected_measurements"]], ["A", "B"])
        rows[0]["NAMES"] = "wrong"
        with self.assertRaises(InputError):
            self.native(rows)

    def test_missing_selected_pose_not_replaced_by_better_score(self):
        result = self.native([self.row(pose=1, score=-20)], qualified=True, verified={(1, 1)})
        self.assertEqual(result["selected_measurements"][0]["status"], "UNAVAILABLE")

    def test_contradictory_duplicate_or_failure_success_rows_rejected(self):
        for rows in ([self.row(), self.row()], [self.row(), self.row(pose=-1, score=100)]):
            with self.subTest(rows=rows), self.assertRaises(InputError):
                self.native(rows)

    def test_prepared_csv_has_exact_public_headers_and_bound_input_order(self):
        rows = [{"identity": "CC", "smiles": "CC", "valid": True},
                {"identity": "CCC", "smiles": "CCC", "valid": True}]
        prepared = prepare_basic_vina_csv(rows)
        decoded = csv_records(prepared["csv_bytes"], {"SMILES", "NAMES"})
        self.assertEqual(list(decoded[0]), ["SMILES", "NAMES"])
        self.assertEqual([r["SMILES"] for r in decoded], ["CC", "CCC"])
        self.assertEqual(prepared["csv_sha256"], sha256(prepared["csv_bytes"]))
        self.assertEqual([r["NAMES"] for r in decoded], [r["NAMES"] for r in prepared["input_manifest"]])
        with self.assertRaises(InputError):
            prepare_basic_vina_csv(rows + rows)


class ArchiveReplay(unittest.TestCase):
    def bundle(self, root):
        method = "RDKit fixture; pinned descriptor implementations/models"
        metrics = [metric(case_id="p38_1a9u", method_version=method),
                   metric(case_id="p38_1a9u", metric_id="logp", value="2", method_version=method),
                   metric(case_id="p38_1a9u", candidate_id="control", canonical_identity="CO",
                          phase="control", method_version=method)]
        run = {"run_id": CONTEXT["run_id"], "scorer": {"rdkit_version": "fixture",
               "version_stdout": "smina 2020.12.10", "descriptor_implementations": {
                   "qed": "rdkit.Chem.QED.qed", "logp": "rdkit.Chem.Crippen.MolLogP"}}}
        files = {"candidate_registry.csv": as_csv(REGISTRY_FIELDS, registry()),
                 "comparison_metrics.csv": as_csv(METRIC_FIELDS, metrics),
                 "run_manifest.json": json.dumps(run).encode()}
        for name, raw in files.items():
            (root / name).write_bytes(raw)
        manifest = [{"relative_path": name, "bytes": str(len(raw)), "sha256": sha256(raw)}
                    for name, raw in files.items()]
        (root / "artifact_manifest.csv").write_bytes(as_csv(["relative_path", "bytes", "sha256"], manifest))
        return files

    def test_artificial_archive_stays_frozen_with_all_records_and_no_restored_allowance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = self.bundle(root)
            imported, receipt = import_p38_archive(root)
            self.assertEqual(len(imported["observations"]), 3)
            self.assertEqual(receipt["archive_decision"]["disposition"], "STOP")
            self.assertFalse(receipt["allowances_restored"])
            self.assertEqual(receipt["qualified_record_coverage"]["search"]["vina"], 0)
            self.assertEqual(receipt["qualified_record_coverage"]["search"]["solubility"], 0)
            self.assertEqual({name: (root / name).read_bytes() for name in files}, files)

    def test_manifest_symlink_outside_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "bundle"
            root.mkdir()
            outside = parent / "outside.csv"
            outside.write_text("relative_path,bytes,sha256\n")
            (root / "artifact_manifest.csv").symlink_to(outside)
            with self.assertRaises(InputError):
                import_p38_archive(root)

    def test_tampered_actual_source_member_is_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.bundle(root)
            (root / "comparison_metrics.csv").write_bytes(b"altered")
            with self.assertRaises(InputError):
                import_p38_archive(root)


if __name__ == "__main__":
    unittest.main()
