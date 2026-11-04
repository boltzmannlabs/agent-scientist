from copy import deepcopy
import json
import unittest

from pilot.context import build_context


def fixture():
    summaries = [{"candidate_id": "c1", "status": "completed", "values": {"qed": 0.123456789012345}},
                 {"candidate_id": "c2", "status": "completed", "values": {"qed": 0.25}}]
    observations = [{"id": cid + "-qed-v1", "candidate_id": cid, "form_id": cid + "-form", "endpoint": "qed",
                     "value": summary["values"]["qed"], "status": "completed", "qualifier": "=",
                     "unit": "dimensionless", "uncertainty": None, "source": "explicit test fixture"}
                    for cid, summary in zip(("c1", "c2"), summaries)]
    rows = [{"row_index": i, "artifact_sha256": "fixture-bytes", "row_id": f"row-fixture-bytes-{i}",
             "candidate_id": cid, "representation": smi, "status": status,
             "source_columns": {"SMILES": smi, "note": "retained extra field"},
             **({"assessment": summaries[0]} if cid == "c1" else {})}
            for i, (cid, smi, status) in enumerate((("c1", "CCO", "new"), ("c1", "OCC", "duplicate"),
                                                    (None, "BAD", "invalid")), 1)]
    cache = {smi: {"candidate": {"id": cid, "form_id": cid + "-form", "representation": smi}}
             for cid, smi in (("c1", "CCO"), ("c2", "CCN"))}
    return {"assessment": {"summaries": summaries, "observations": observations},
            "rows": rows, "cache": cache, "artifact_sha256": "fixture-bytes"}


class ContextTests(unittest.TestCase):
    def test_repeated_assay_metadata_shrinks_without_selecting_candidates(self):
        source = fixture()
        source["assessment"]["summaries"] = []
        source["assessment"]["observations"] = []
        source["cache"] = {}
        source["rows"] = []
        for i in range(40):
            cid = f"ARTIFICIAL-{i}"
            form = f"NOT-A-MOLECULE-{i}"
            source["assessment"]["summaries"].append({"candidate_id": cid, "status": "completed", "values": {"qed": i / 100}})
            source["assessment"]["observations"].append({"id": cid + "-qed-v1", "candidate_id": cid, "form_id": cid,
                "endpoint": "qed", "value": i / 100, "status": "completed", "qualifier": "=",
                "method": "ARTIFICIAL-METHOD", "source": "Repeated fixture metadata; no molecule was scored. " * 8})
            source["cache"][form] = {"candidate": {"id": cid, "form_id": cid, "representation": form}}
            source["rows"].append({"row_index": i + 1, "candidate_id": cid, "status": "new", "source_columns": {"SMILES": form}})
        result = build_context(source)
        full_view = {"observations": source["assessment"], "returned_rows": source["rows"]}
        self.assertLess(len(json.dumps(result)), len(json.dumps(full_view)))
        self.assertEqual(result["observations"]["summaries"], source["assessment"]["summaries"])
        self.assertEqual(result["returned_rows"]["total_rows"], 40)

    def test_all_scores_forms_rows_and_extra_fields_survive_without_mutating_source(self):
        source = fixture(); original = deepcopy(source); compact = build_context(source)
        self.assertEqual(compact["observations"]["summaries"], source["assessment"]["summaries"])
        self.assertEqual(compact["candidate_forms"]["c1"]["form_id"], "c1-form")
        projected = []
        for table in compact["returned_rows"]["tables"]:
            projected.extend({**table["shared_fields"], **dict(zip(table["columns"], values))}
                             for values in table["records"])
        self.assertEqual(sorted(r["row_index"] for r in projected), [1, 2, 3])
        self.assertEqual({r["status"] for r in projected}, {"new", "duplicate", "invalid"})
        self.assertTrue(all(r["source_columns"]["note"] == "retained extra field" for r in projected))
        self.assertEqual(source, original)
        changed = deepcopy(source); changed["rows"][2]["source_columns"]["note"] = "changed"
        self.assertNotEqual(build_context(changed)["evidence_binding"], compact["evidence_binding"])

    def test_conflicting_or_variable_uncertainty_observations_are_not_hidden(self):
        source = fixture()
        self.assertEqual(build_context(source)["observations"]["measurements"][0]["points"], "all_completed_summaries")
        source["assessment"]["observations"][0]["uncertainty"] = 0.2
        result = build_context(source)
        self.assertEqual(result["observations"]["measurements"][0]["records"], source["assessment"]["observations"])
        source["assessment"]["observations"][0]["value"] = 0.9
        result = build_context(source)
        self.assertEqual(result["observations"]["measurements"][0]["records"][0]["value"], 0.9)


if __name__ == "__main__":
    unittest.main()
