"""Scientifically complete compact view; full original evidence stays host-owned."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def build_context(batch):
    assessment = deepcopy(batch["assessment"])
    summaries = {x["candidate_id"]: x for x in assessment["summaries"]}
    completed = [x["candidate_id"] for x in assessment["summaries"] if x.get("status") == "completed"]
    forms = {}
    for graph, entry in batch.get("cache", {}).items():
        if isinstance(entry, dict) and "candidate" in entry:
            candidate = entry["candidate"]
            cid = candidate["id"]
            if cid in summaries:
                forms[cid] = {"candidate_id": cid, "form_id": candidate["form_id"], "canonical_form": graph}
                if candidate["representation"] != graph:
                    forms[cid]["representation"] = candidate["representation"]
    by_endpoint = defaultdict(list)
    for observation in assessment.pop("observations", []):
        by_endpoint[observation.get("endpoint")].append(observation)
    measurements = []
    for endpoint, observations in by_endpoint.items():
        identities = {"id", "candidate_id", "form_id", "value"}
        metadata = {k: v for k, v in observations[0].items() if k not in identities}
        ids = [o.get("candidate_id") for o in observations]
        factorable = len(ids) == len(set(ids)) and all(
            o.get("id") == str(o.get("candidate_id")) + "-" + str(endpoint) + "-v1"
            and o.get("candidate_id") in forms
            and o.get("form_id") == forms[o["candidate_id"]]["form_id"]
            and endpoint in summaries[o["candidate_id"]].get("values", {})
            and o.get("value") == summaries[o["candidate_id"]]["values"][endpoint]
            and {k: v for k, v in o.items() if k not in identities} == metadata
            for o in observations)
        if factorable:
            measurements.append({"metadata": metadata,
                                 "points": "all_completed_summaries" if ids == completed else ids,
                                 "value_reference": "summaries[candidate_id].values[endpoint]",
                                 "form_reference": "candidate_forms[candidate_id].form_id",
                                 "id_template": "{candidate_id}-" + str(endpoint) + "-v1"})
        else:
            # Conflicting values, censoring, variable uncertainty/provenance or
            # unusual identifiers must remain visible, not be 'summarized' away.
            measurements.append({"records": observations})
    assessment["measurements"] = measurements
    row_groups = defaultdict(list)
    omitted = set()
    for original in batch["rows"]:
        row = deepcopy(original)
        cid = row.get("candidate_id")
        if cid in summaries and "assessment" in row and row["assessment"] == summaries[cid]:
            row.pop("assessment")
            omitted.add("row.assessment: identical to observations.summaries keyed by candidate_id")
        if "artifact_sha256" in row and row["artifact_sha256"] == batch.get("artifact_sha256"):
            row.pop("artifact_sha256", None)
            omitted.add("row.artifact_sha256: identical to evidence_binding.artifact_sha256")
        expected = f"row-{batch.get('artifact_sha256')}-{row.get('row_index')}"
        if "row_id" in row and row["row_id"] == expected:
            row.pop("row_id")
            omitted.add("row.row_id: row-{artifact_sha256}-{row_index}")
        source = row.get("source_columns")
        if isinstance(source, dict) and "SMILES" in source and "representation" in row and row["representation"] == source["SMILES"]:
            row.pop("representation", None)
            omitted.add("row.representation: identical to row.source_columns.SMILES")
        row_groups[tuple(sorted(row))].append(row)
    tables = []
    for fields, rows in row_groups.items():
        shared = {k: rows[0][k] for k in fields if all(r[k] == rows[0][k] for r in rows)}
        columns = [k for k in fields if k not in shared]
        tables.append({"shared_fields": shared, "columns": columns,
                       "records": [[r[k] for k in columns] for r in rows], "row_count": len(rows)})
    return {"observations": assessment, "candidate_forms": forms,
            "returned_rows": {"tables": tables, "total_rows": len(batch["rows"])},
            "evidence_binding": {"full_batch_sha256": digest(batch),
                                 "full_assessment_sha256": digest(batch["assessment"]),
                                 "full_returned_rows_sha256": digest(batch["rows"]),
                                 "artifact_sha256": batch.get("artifact_sha256")},
            "context_projection": {"all_returned_rows_retained": True,
                                   "repeated_transport_fields_factored": sorted(omitted),
                                   "measurement_order": "Original order retained in bound private ledger; point associations preserved here",
                                   "full_private_evidence_access": "Host-owned; this digest does not give the model file access",
                                   "selection_or_truncation": "none"}}
