"""Pinned local assessment and exact-form CSV intake for the development pilot.

The original task scorer is reused read-only. This module does no generation,
remote execution, experimental interpretation or expert-review certification.
"""
from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path

from rdkit import Chem, rdBase
from prototype.library_audit.audit import audit_bytes, normalization_policy_id, _parser


SCORER_SHA256 = "71855efd492c8af40f96f8a7ffcd271083087a55081887a51ca66d628c35765c"
MODEL_SHA256 = "0878479f24da0c09ad85a6fc4b992faeb02ec426465c7f79008e969da4e40f76"
LEAD_SHA256 = "46b6a09d344b2bd9c69a8df152fc5bfe30006b590a3014a2333ca2a16e2ccb39"
MAX_CSV_BYTES = 64 * 1024 * 1024  # Inspection limit; never truncate to this size.
METRICS = ("drd2_p_active", "qed", "lead_similarity")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _qualified(values, baseline):
    return (values["drd2_p_active"] > baseline["drd2_p_active"]
            and values["qed"] > baseline["qed"] and values["lead_similarity"] > 0.7)


def _identity(value):
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(["SMILES"]); writer.writerow([value])
    report = audit_bytes(stream.getvalue().encode())
    if report["invalid_rows"]:
        return None, "invalid", "Empty or unparseable molecular representation"
    if report["unsupported_rows"]:
        return None, "unresolved", "Unsupported or discarded identity feature; no score assigned"
    if report["multicomponent_rows"]:
        return None, "invalid", "Disconnected representation is outside this task"
    if not report["normalized_identity_complete"]:
        return None, "unresolved", "Complete molecular identity was not established"
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(value, _parser())
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True), None, None


class PinnedAssessor:
    def __init__(self, config):
        self.config = deepcopy(config)
        self._check_files()
        spec = importlib.util.spec_from_file_location("pilot_pinned_drd2_scorer", config["scorer_path"])
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        if self.module.MODEL_SHA256 != MODEL_SHA256 or self.module.METHOD_VERSION != config["method_version"]:
            raise ValueError("Pinned assessor model or runtime signature mismatch")
        self.lead = json.loads(Path(config["lead_path"]).read_text())
        self.lead_graph, status, _ = _identity(self.lead["representation"])
        if status:
            raise ValueError("Original reference identity is not qualified")
        baseline = config.get("baseline")
        if (not isinstance(baseline, dict) or not all(k in baseline for k in METRICS)
                or any(type(baseline[k]) not in (int, float) or not math.isfinite(baseline[k]) for k in METRICS)):
            raise ValueError("Explicit finite original baseline values required")
        self.binding = digest({"model": MODEL_SHA256, "scorer": SCORER_SHA256,
                               "lead": LEAD_SHA256, "method_version": config["method_version"],
                               "baseline": {k: baseline[k] for k in METRICS},
                               "normalization": normalization_policy_id(),
                               "identity_implementation": file_sha(audit_bytes.__code__.co_filename),
                               "intake_implementation": file_sha(__file__)})

    def _check_files(self):
        for key, expected in (("scorer", SCORER_SHA256), ("model", MODEL_SHA256), ("lead", LEAD_SHA256)):
            if self.config.get(key + "_sha256") != expected:
                raise ValueError("Unexpected pinned " + key + " identity")
            path = Path(self.config[key + "_path"])
            if not path.is_file() or file_sha(path) != expected:
                raise ValueError("Pinned " + key + " file missing or changed")

    def _validate_assessment(self, result):
        if result["model_sha256"] != MODEL_SHA256 or result["method_version"] != self.config["method_version"]:
            raise ValueError("Returned assessment identity mismatch")
        actual = result["summaries"][0]["values"]
        if any(actual[k] != self.config["baseline"][k] for k in METRICS):
            raise ValueError("Original baseline no longer reproduces exactly")
        for row in result["summaries"]:
            if row["status"] != "completed":
                continue
            values = row["values"]
            if any(type(values[k]) not in (int, float) or not math.isfinite(values[k])
                   or not 0 <= values[k] <= 1 for k in METRICS):
                raise ValueError("Non-finite or out-of-range assessor value")
        json.dumps(result, allow_nan=False)

    def baseline_check(self):
        self._check_files()
        result = self.module.assess_records(self.config["model_path"], self.lead, [])
        self._validate_assessment(result)
        return {**result, "scorer_kind": "pinned_drd2", "baseline_model_evaluations": 1,
                "new_unique_candidate_evaluations": 0}

    def _entry(self, graph, candidate, summary, observations):
        entry = {"binding": self.binding, "canonical_form": graph, "candidate": candidate,
                 "summary": summary, "observations": observations}
        return {**entry, "entry_sha256": digest(entry)}

    def _checked_cache(self, supplied):
        if supplied is None:
            return {}
        if not isinstance(supplied, dict):
            raise ValueError("Assessment cache must be a form-indexed object")
        cache = deepcopy(supplied)
        for graph, entry in cache.items():
            if not isinstance(graph, str) or not isinstance(entry, dict):
                raise ValueError("Malformed cached form")
            raw = {k: v for k, v in entry.items() if k != "entry_sha256"}
            if (entry.get("binding") != self.binding or entry.get("canonical_form") != graph
                    or entry.get("entry_sha256") != digest(raw)):
                raise ValueError("Stale or altered cached assessment")
            parsed, status, _ = _identity(entry["candidate"]["representation"])
            expected_id = self.lead["id"] if graph == self.lead_graph else "candidate-" + digest(graph)
            if (status or parsed != graph or entry["candidate"].get("id") != expected_id
                    or entry["summary"].get("candidate_id") != expected_id):
                raise ValueError("Cached candidate/form association mismatch")
            values = entry["summary"]["values"]
            if any(type(values.get(k)) not in (int, float) or not math.isfinite(values[k])
                   or not 0 <= values[k] <= 1 for k in METRICS):
                raise ValueError("Non-finite or out-of-range cached scores")
            expected_metrics = {*METRICS, "lead_similarity_gt_0_7"}
            if values.get("lead_similarity_gt_0_7") != int(values["lead_similarity"] > 0.7):
                raise ValueError("Cached similarity indicator disagrees with its raw value")
            observations = entry.get("observations")
            if (not isinstance(observations, list) or len(observations) != len(expected_metrics)
                    or {o.get("endpoint") for o in observations} != expected_metrics):
                raise ValueError("Incomplete or repeated cached observations")
            signatures = self.module.signatures()
            for o in observations:
                endpoint = o["endpoint"]
                if (o.get("candidate_id") != expected_id
                        or o.get("form_id") != entry["candidate"]["form_id"]
                        or o.get("value") != values[endpoint]
                        or o.get("qualifier") != "=" or o.get("status") != "completed"
                        or any(o.get(k) != v for k, v in signatures[endpoint].items())):
                    raise ValueError("Cached observation association or value mismatch")
            qualifies = graph != self.lead_graph and _qualified(values, self.config["baseline"])
            if entry["summary"].get("qualified_improvement") is not qualifies:
                raise ValueError("Cached success flag disagrees with the fixed rules")
        return cache

    def assess_csv(self, path, cache=None):
        """Score new exact forms once; preserve all rows and cached provenance.

        Cache bindings/checksums establish consistency, not independent trust.
        The owning runner must protect its state and record artifact receipts.
        """
        self._check_files()
        cache = self._checked_cache(cache)
        path = Path(path)
        with path.open("rb") as handle:
            raw = handle.read(MAX_CSV_BYTES + 1)
        if not raw or len(raw) > MAX_CSV_BYTES:
            raise ValueError("CSV must be nonempty and within the 64 MiB inspection bound; no rows were truncated")
        artifact_sha = hashlib.sha256(raw).hexdigest()
        try:
            records = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValueError("Valid UTF-8 CSV required") from exc
        if not records or records[0].count("SMILES") != 1 or len(set(records[0])) != len(records[0]):
            raise ValueError("Exactly one case-sensitive unambiguous SMILES header required")
        header = records[0]
        if any(len(row) != len(header) for row in records[1:]):
            raise ValueError("Every CSV record must match the header width")
        rows, new, first_rows = [], {}, {}
        for ordinal, fields in enumerate(records[1:], 1):
            data = dict(zip(header, fields)); value = data["SMILES"]
            graph, status, reason = _identity(value)
            row = {"row_index": ordinal, "row_id": f"row-{artifact_sha}-{ordinal}",
                   "artifact_sha256": artifact_sha, "source_columns": data,
                   "representation": value, "canonical_form": graph,
                   "candidate_id": None, "status": status, "reason": reason,
                   "edit_attribution": "unknown"}
            rows.append(row)
            if status:
                continue
            cid = self.lead["id"] if graph == self.lead_graph else "candidate-" + digest(graph)
            row["candidate_id"] = cid
            if graph == self.lead_graph or graph in cache or graph in new:
                row.update(status="duplicate", duplicate_of=cid,
                           first_artifact_row_id=first_rows.get(graph))
            else:
                row["status"] = "new"
                first_rows[graph] = row["row_id"]
                new[graph] = {"id": cid, "form_id": "canonical-isomeric-" + digest(graph),
                              "representation": value, "reference_id": self.lead["id"],
                              "source": f"CSV artifact SHA256 {artifact_sha}, data row {ordinal}; generator provenance supplied by owning runner"}
        # The fixed helper scores its baseline once per invocation. Keep this
        # real overhead separate from newly evaluated candidate counts.
        result = self.module.assess_records(self.config["model_path"], self.lead, list(new.values()))
        self._validate_assessment(result)
        summaries = {r["candidate_id"]: r for r in result["summaries"]}
        for graph, candidate in [(self.lead_graph, self.lead), *new.items()]:
            cid = candidate["id"]
            summary = summaries[cid]
            observations = [o for o in result["observations"] if o["candidate_id"] == cid]
            cache[graph] = self._entry(graph, deepcopy(candidate), deepcopy(summary), deepcopy(observations))
        for row in rows:
            if row["canonical_form"] is not None:
                row["assessment"] = deepcopy(cache[row["canonical_form"]]["summary"])
        qualifiers = sorted({r["candidate_id"] for r in rows if r.get("assessment", {}).get("qualified_improvement")})
        return {"rows": rows, "assessment": result, "cache": cache,
                "new_unique_candidate_evaluations": len(new), "baseline_model_evaluations": 1,
                "total_model_row_evaluations": len(new) + 1,
                "raw_rows": len(rows), "invalid_rows": sum(r["status"] == "invalid" for r in rows),
                "unresolved_rows": sum(r["status"] == "unresolved" for r in rows),
                "duplicate_rows": sum(r["status"] == "duplicate" for r in rows),
                "qualified_candidate_ids": qualifiers, "artifact_sha256": artifact_sha,
                "scorer_kind": "pinned_drd2", "identity_policy": normalization_policy_id(),
                "source_authenticity": "bound by owning runner; not authenticated by local CSV scoring",
                "chemical_expert_review": "not_claimed"}
