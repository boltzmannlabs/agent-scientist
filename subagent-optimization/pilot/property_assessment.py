"""Import platform property results and compute local secondary task metrics.

No predictor is invoked here. Platform values are raw model scores with unverified
physical units and weight revision. Cache integrity is not source authentication:
the owning runner must bind artifacts to its private connector receipts.
"""
from copy import deepcopy
import csv
import hashlib
import io
import math
from pathlib import Path

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import QED, rdFingerprintGenerator

from pilot.assessment import MAX_CSV_BYTES, _identity, digest, file_sha
from prototype.library_audit.audit import audit_bytes, normalization_policy_id, _parser


KIND = "platform_lipophilicity_rdkit_v1"


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _qualified(values, baseline, target_min=0, target_max=3):
    return (all(_finite(values.get(k)) for k in ("lipophilicity", "qed", "lead_similarity"))
            and target_min <= values["lipophilicity"] <= target_max
            and values["qed"] > baseline["qed"] and values["lead_similarity"] > 0.7)


class PlatformPropertyAssessor:
    def __init__(self, config):
        self.config = deepcopy(config)
        for field, path in (("implementation_sha256", __file__),
                            ("identity_implementation_sha256", _identity.__code__.co_filename)):
            if field in config and config[field] != file_sha(path):
                raise ValueError("Frozen property assessment implementation changed")
        if config.get("kind") != KIND or config.get("property_column") != "Lipophilicity":
            raise ValueError("Explicit supported platform property assessor kind/column required")
        if config.get("rdkit_version") != rdBase.rdkitVersion:
            raise ValueError("RDKit runtime does not match the frozen assessor configuration")
        if (not _finite(config.get("target_min")) or not _finite(config.get("target_max"))
                or config["target_min"] > config["target_max"]):
            raise ValueError("Finite ordered property-score target range required")
        self.baseline = config.get("baseline")
        if (not isinstance(self.baseline, dict)
                or any(not _finite(self.baseline.get(k)) for k in ("lipophilicity", "qed", "lead_similarity"))):
            raise ValueError("Finite verified original baseline values required")
        self.lead = deepcopy(config["reference"])
        if not all(isinstance(self.lead.get(k), str) and self.lead[k] for k in ("id", "representation", "form_id")):
            raise ValueError("Original reference identity and form required")
        self.lead_graph, status, _ = _identity(self.lead["representation"])
        if status:
            raise ValueError("Original reference identity is not qualified")
        self.generator = rdFingerprintGenerator.GetMorganGenerator(radius=2)
        self.lead_fp = self.generator.GetSparseCountFingerprint(Chem.MolFromSmiles(self.lead_graph, _parser()))
        qed, similarity = self._local(self.lead_graph)
        if qed != self.baseline["qed"] or similarity != self.baseline["lead_similarity"] or similarity != 1.0:
            raise ValueError("Original reference local metrics do not reproduce the frozen baseline")
        self.binding = digest({"config": self.config, "rdkit": rdBase.rdkitVersion,
                               "normalization": normalization_policy_id(),
                               "identity_implementation": file_sha(audit_bytes.__code__.co_filename),
                               "identity_intake_implementation": file_sha(_identity.__code__.co_filename),
                               "assessment_implementation": file_sha(__file__)})

    def _local(self, graph):
        # Preserve the original reference's atom ordering so its floating-point
        # QED reproduces the original fixed value exactly.
        representation = self.lead["representation"] if graph == self.lead_graph else graph
        mol = Chem.MolFromSmiles(representation, _parser())
        return (QED.qed(mol), DataStructs.TanimotoSimilarity(
            self.generator.GetSparseCountFingerprint(mol), self.lead_fp))

    def _entry(self, graph, candidate, evidence):
        qed, similarity = self._local(graph)
        finite_scores = {e["reported_value"] for e in evidence if e["reported_value"] is not None}
        is_reference = graph == self.lead_graph
        if is_reference:
            finite_scores.add(self.baseline["lipophilicity"])
        conflict = len(finite_scores) > 1
        score = next(iter(finite_scores)) if len(finite_scores) == 1 else None
        values = {"lipophilicity": score, "qed": qed, "lead_similarity": similarity,
                  "lead_similarity_gt_0_7": int(similarity > 0.7),
                  "lipophilicity_in_target_range": (None if score is None else int(
                      self.config["target_min"] <= score <= self.config["target_max"]))}
        summary = {"candidate_id": candidate["id"], "form_id": candidate["form_id"],
                   "status": "completed" if score is not None else "unresolved", "values": values,
                   "qualified_improvement": bool(not is_reference and not conflict and _qualified(
                       values, self.baseline, self.config["target_min"], self.config["target_max"])),
                   "property_prediction_conflict": conflict,
                   "reported_property_values": sorted(finite_scores),
                   "reason": ("Conflicting reported property values for the same exact form" if conflict
                              else "No finite platform property score" if score is None else None),
                   "uncertainty": "not_reported", "physical_units": "unverified",
                   "platform_model_weight_revision": "unverified"}
        entry = {"binding": self.binding, "canonical_form": graph, "candidate": deepcopy(candidate),
                 "summary": summary, "observations": [], "property_evidence": deepcopy(evidence)}
        return {**entry, "entry_sha256": digest(entry)}

    def _checked_cache(self, supplied):
        if supplied is None:
            return {}
        if not isinstance(supplied, dict):
            raise ValueError("Assessment cache must be a form-indexed object")
        cache = deepcopy(supplied)
        for graph, entry in cache.items():
            if not isinstance(entry, dict) or entry.get("binding") != self.binding:
                raise ValueError("Stale or cross-configuration assessment cache")
            candidate = entry.get("candidate", {})
            parsed, status, _ = _identity(candidate.get("representation", ""))
            cid = self.lead["id"] if graph == self.lead_graph else "candidate-" + digest(graph)
            form = self.lead["form_id"] if graph == self.lead_graph else "canonical-isomeric-" + digest(graph)
            if status or parsed != graph or candidate.get("id") != cid or candidate.get("form_id") != form:
                raise ValueError("Cached exact-form identity mismatch")
            evidence = entry.get("property_evidence")
            if not isinstance(evidence, list) or len({e.get("row_id") for e in evidence}) != len(evidence):
                raise ValueError("Malformed or repeated cached property evidence")
            for e in evidence:
                if (not isinstance(e.get("row_id"), str) or not isinstance(e.get("artifact_sha256"), str)
                        or not isinstance(e.get("reported_text"), str)
                        or (e.get("reported_value") is not None and not _finite(e["reported_value"]))):
                    raise ValueError("Malformed cached property provenance")
                try:
                    parsed_value = float(e["reported_text"])
                    parsed_value = parsed_value if math.isfinite(parsed_value) else None
                except ValueError:
                    parsed_value = None
                if parsed_value != e["reported_value"]:
                    raise ValueError("Cached raw property text/value disagree")
            if entry != self._entry(graph, candidate, evidence):
                raise ValueError("Altered cached assessment or provenance")
        return cache

    def _assessment(self, cache):
        return {"summaries": [deepcopy(e["summary"]) for e in cache.values()], "observations": [],
                "measurements": [], "scorer_kind": KIND, "rdkit_version": rdBase.rdkitVersion,
                "property_interpretation": "raw platform model score; physical units and weight revision unverified",
                "secondary_method": "RDKit QED; sparse Morgan count radius=2 Tanimoto; exact supplied forms",
                "uncertainty": "not_reported", "source_binding": self.binding}

    def baseline_check(self):
        entry = self._entry(self.lead_graph, self.lead, [])
        return {**self._assessment({self.lead_graph: entry}), "baseline_model_evaluations": 0,
                "new_unique_candidate_evaluations": 0, "reference_identity_verified": True,
                "baseline_property_source": "frozen verified platform reference; not recomputed locally"}

    def assess_csv(self, path, cache=None):
        cache = self._checked_cache(cache)
        cache.setdefault(self.lead_graph, self._entry(self.lead_graph, self.lead, []))
        old_completed = {g for g, e in cache.items() if e["summary"]["status"] == "completed"}
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_CSV_BYTES + 1)
        if not raw or len(raw) > MAX_CSV_BYTES:
            raise ValueError("Nonempty CSV within the 64 MiB inspection bound required; no truncation")
        artifact_sha = hashlib.sha256(raw).hexdigest()
        try:
            records = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValueError("Valid UTF-8 CSV required") from exc
        if (not records or len(set(records[0])) != len(records[0])
                or records[0].count("SMILES") != 1 or records[0].count(self.config["property_column"]) != 1):
            raise ValueError("Unique exact SMILES and Lipophilicity headers required")
        header = records[0]
        if any(len(row) != len(header) for row in records[1:]):
            raise ValueError("Every CSV record must match the header width")
        rows, seen, reported = [], set(cache), 0
        for ordinal, fields in enumerate(records[1:], 1):
            data = dict(zip(header, fields)); value = data["SMILES"]
            graph, status, reason = _identity(value)
            score_text = data[self.config["property_column"]]
            try:
                score = float(score_text)
                score = score if math.isfinite(score) else None
            except ValueError:
                score = None
            reported += score is not None
            row = {"row_index": ordinal, "row_id": f"row-{artifact_sha}-{ordinal}",
                   "artifact_sha256": artifact_sha, "source_columns": data,
                   "representation": value, "canonical_form": graph, "candidate_id": None,
                   "status": status, "reason": reason, "edit_attribution": "unknown",
                   "reported_property_value": score, "is_duplicate": False}
            rows.append(row)
            if status:
                continue
            cid = self.lead["id"] if graph == self.lead_graph else "candidate-" + digest(graph)
            row.update(candidate_id=cid, is_duplicate=graph in seen,
                       status="duplicate" if graph in seen else "new")
            if row["is_duplicate"]:
                row["duplicate_of"] = cid
            seen.add(graph)
            candidate = (cache[graph]["candidate"] if graph in cache else {
                "id": cid, "form_id": "canonical-isomeric-" + digest(graph), "representation": value,
                "reference_id": self.lead["id"],
                "source": f"CSV artifact SHA256 {artifact_sha}, data row {ordinal}; receipt bound by owning runner"})
            evidence = deepcopy(cache[graph]["property_evidence"]) if graph in cache else []
            new_evidence = {"row_id": row["row_id"], "artifact_sha256": artifact_sha,
                            "reported_text": score_text, "reported_value": score}
            by_id = {e["row_id"]: e for e in evidence}
            if row["row_id"] in by_id and by_id[row["row_id"]] != new_evidence:
                raise ValueError("Artifact row provenance conflicts with existing evidence")
            if row["row_id"] not in by_id:
                evidence.append(new_evidence)
            cache[graph] = self._entry(graph, candidate, evidence)
            if score is None:
                row.update(status="unresolved", reason="Missing, nonnumeric or nonfinite platform property score")
        reference_conflict = cache[self.lead_graph]["summary"]["property_prediction_conflict"]
        for row in rows:
            graph = row["canonical_form"]
            if graph is None:
                continue
            row["assessment"] = deepcopy(cache[graph]["summary"])
            if row["assessment"]["property_prediction_conflict"]:
                row.update(status="unresolved", reason=row["assessment"]["reason"])
        qualifiers = sorted(e["candidate"]["id"] for e in cache.values()
                            if e["summary"]["qualified_improvement"] and not reference_conflict)
        return {"rows": rows, "assessment": self._assessment(cache), "cache": cache,
                "new_unique_candidate_evaluations": sum(g != self.lead_graph and g not in old_completed
                    and e["summary"]["status"] == "completed" for g, e in cache.items()),
                "baseline_model_evaluations": 0, "total_model_row_evaluations": None,
                "reported_property_prediction_rows": reported, "internal_model_evaluations": "unknown",
                "evaluation_count_semantics": "new uniquely resolved nonreference forms imported; not backend model calls",
                "raw_rows": len(rows), "invalid_rows": sum(r["status"] == "invalid" for r in rows),
                "unresolved_rows": sum(r["status"] == "unresolved" for r in rows),
                "duplicate_rows": sum(r["is_duplicate"] for r in rows),
                "qualified_candidate_ids": qualifiers, "artifact_sha256": artifact_sha,
                "scorer_kind": KIND, "identity_policy": normalization_policy_id(),
                "reference_score_conflict": reference_conflict,
                "evaluation_blockers": ["original_reference_property_conflict"] if reference_conflict else [],
                "source_authenticity": "bound by owning runner; not authenticated by CSV intake",
                "chemical_expert_review": "not_claimed"}
