"""Offline BASELINE: contextual edit evidence selects an UNTRIED library.

No chemistry inference, prediction, file/API/DB I/O, execution or native schema.
Annotations, identity, admissibility and content digests are trusted host inputs.
"""
from fractions import Fraction
import hashlib
import json
import math


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def signature(task):
    keys = ("task_id", "reference_id", "context_id", "assessor_id", "filter_protocol",
            "family_definition_id", "library_identity_policy_id", "generation_settings", "objectives", "constraints")
    return _digest({key: task[key] for key in keys})


def action_signature(library):
    keys = ("id", "asset_ref", "content_sha256", "context_id", "target_family",
            "family_definition_id", "capability_card_reviewed", "normalization_policy_id",
            "normalized_input_set_sha256")
    return _digest({key: library[key] for key in keys})


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _passes(values, rule):
    x, y = values[rule["metric"]], rule["threshold"]
    return {"gt": x > y, "ge": x >= y, "lt": x < y, "le": x <= y}[rule["operator"]]


def choose_library(task, libraries, batches, strategy="context_coverage"):
    """Choose one untried asset, stop on first success, or explicitly abstain.

    Marginal family coverage is a transfer hypothesis, not joint-hit probability
    or a guarantee the next library generates a specified edit/site/scaffold.
    """
    require(strategy in {"context_coverage", "round_robin"}, "Unknown strategy")
    require(task.get("state") in {"active", "closed", "frozen", "satisfied"}, "Task state required")
    out = {"strategy": strategy, "disposition": None, "library_id": None, "reason": None,
           "family_profiles": {}, "library_states": {}, "warnings": [],
           "cross_library_overlap": {}, "qualifying_ids": [], "execution": "not_performed",
           "scientific_benefit": "not_assessed", "resource_limits_enforced": False,
           "internal_compute": "unknown"}
    if task["state"] != "active":
        return {**out, "disposition": "not_applicable", "reason": "task_terminal"}
    require(task.get("stop_on_first_success") is True, "Explicit first-success task required")
    require(task["objectives"] and task["constraints"], "Explicit task rules required")
    rules = task["objectives"] + task["constraints"]
    for rule in rules:
        require(rule.get("operator") in {"gt", "ge", "lt", "le"}
                and isinstance(rule.get("metric"), str) and _number(rule.get("threshold")), "Invalid rule")
    metrics = sorted({rule["metric"] for rule in rules})
    expected_signature = signature(task)
    manifest = {}
    for lib in libraries:
        lid = lib.get("id")
        require(isinstance(lid, str) and lid and lid not in manifest, "Invalid/duplicate library ID")
        require(isinstance(lib.get("asset_ref"), str) and lib["asset_ref"], "Asset required")
        for hash_key in ("content_sha256", "normalized_input_set_sha256"):
            sha = lib.get(hash_key)
            require(isinstance(sha, str) and len(sha) == 64
                    and all(c in "0123456789abcdef" for c in sha), "Content/normalized SHA256 required")
        for key in ("context_id", "target_family", "family_definition_id", "normalization_policy_id"):
            require(isinstance(lib.get(key), str) and lib[key], "Library context/family definition required")
        require(type(lib.get("capability_card_reviewed")) is bool, "Coverage review flag required")
        manifest[lid] = lib
        out["library_states"][lid] = {"attempts": 0, "last_sequence": -1, "statuses": [],
                                     "empty_complete_batches": 0, "unresolved_rows": 0,
                                     "nonisolated_rows": 0, "reference_rows_excluded": 0}
    seen_batches, seen_chemistry, family_rows = {}, {}, {}
    seen_annotations, annotation_conflicts = {}, set()
    qualifiers, fatal, profile_errors = set(), [], []
    for batch in batches:
        bid = batch.get("id")
        require(isinstance(bid, str) and bid, "Batch ID required")
        fingerprint = _digest(batch)
        if bid in seen_batches:
            require(seen_batches[bid] == fingerprint, "Batch ID reused with changed data")
            continue
        seen_batches[bid] = fingerprint
        lid = batch.get("library_id")
        require(lid in manifest, "Unknown source library")
        seq = batch.get("sequence")
        require(type(seq) is int and seq >= 0, "Observed sequence required")
        stat = out["library_states"][lid]
        stat["attempts"] += 1
        stat["last_sequence"] = max(stat["last_sequence"], seq)
        status = batch.get("status")
        require(status in {"complete", "failed", "pending", "unknown"}, "Completion status required")
        stat["statuses"].append(status)
        if batch.get("signature") != expected_signature:
            fatal.append("incompatible_task_or_settings:" + bid)
            continue
        if manifest[lid]["normalization_policy_id"] != task["library_identity_policy_id"]:
            fatal.append("incompatible_library_normalization_policy:" + bid)
            continue
        if batch.get("action_signature") != action_signature(manifest[lid]):
            fatal.append("library_asset_or_coverage_identity_mismatch:" + bid)
            continue
        if batch.get("evidence_admissible") is not True or manifest[lid].get("approved") is not True:
            fatal.append("evidence_not_admitted_by_protocol:" + bid)
            continue
        if status != "complete":
            out["warnings"].append("attempt_" + status + ":" + bid)
            continue
        rows = batch.get("rows")
        require(isinstance(rows, list), "Complete batch requires rows, including []")
        complete = batch.get("complete_output_coverage") is True
        if complete and not rows:
            stat["empty_complete_batches"] += 1
        pending_rows, unresolved, annotation_errors = [], 0, []
        for row in rows:
            cid, values = row.get("chemical_id"), row.get("values", {})
            if not isinstance(cid, str) or not cid or row.get("valid") is not True:
                unresolved += 1
                continue
            if cid == task["reference_id"]:
                stat["reference_rows_excluded"] += 1
                continue
            if not isinstance(values, dict) or not all(k in values and _number(values[k]) for k in metrics):
                unresolved += 1
                continue
            data = {key: values[key] for key in metrics}
            if cid in seen_chemistry and seen_chemistry[cid][0] != data:
                fatal.append("conflicting_same_identity_scores:" + cid)
                continue
            if cid not in seen_chemistry:
                seen_chemistry[cid] = (data, set())
            seen_chemistry[cid][1].add(lid)
            # Complete, admitted winning row may end the task even if another row
            # is unresolved. Whole-batch coverage is required for family profiles.
            if all(_passes(data, rule) for rule in rules):
                qualifiers.add(cid)
            annotation_ok = (row.get("annotation_reviewed") is True
                             and row.get("family_definition_id") == task["family_definition_id"]
                             and row.get("parent_id") == task["reference_id"]
                             and row.get("context_id") == task["context_id"]
                             and type(row.get("single_edit")) is bool)
            if not annotation_ok:
                annotation_errors.append("missing_or_incompatible_edit_annotation:" + cid)
                continue
            attribution = (row["single_edit"], row.get("edit_family") if row["single_edit"] else None,
                           row["parent_id"], row["context_id"], row["family_definition_id"])
            if cid in seen_annotations and seen_annotations[cid] != attribution:
                fatal.append("conflicting_edit_annotation:" + cid)
                annotation_conflicts.add(cid)
                for entries in family_rows.values():
                    entries.pop(cid, None)
                continue
            seen_annotations[cid] = attribution
            if row["single_edit"] is False:
                stat["nonisolated_rows"] += 1
                continue  # Reviewed confounded edits cannot establish isolated family effects.
            family = row.get("edit_family")
            if not isinstance(family, str) or not family:
                annotation_errors.append("missing_edit_family:" + cid)
                continue
            pending_rows.append((family, cid, data))
        stat["unresolved_rows"] += unresolved
        if not complete or unresolved:
            profile_errors.append("incomplete_family_profile_source:" + bid)
        profile_errors.extend(annotation_errors)
        if not complete or unresolved or annotation_errors:
            continue
        for family, cid, data in pending_rows:
            if cid in annotation_conflicts:
                continue
            previous = [key for key, entries in family_rows.items() if cid in entries]
            if previous and family not in previous:
                fatal.append("conflicting_edit_annotation:" + cid)
                continue
            family_rows.setdefault(family, {})[cid] = data

    out["cross_library_overlap"] = {
        cid: sorted(lids) for cid, (_, lids) in seen_chemistry.items() if len(lids) > 1}
    vectors = {}
    for family, entries in family_rows.items():
        if not entries:
            continue
        rows = list(entries.values())
        hard = [all(_passes(row, rule) for rule in task["constraints"]) for row in rows]
        counts = [sum(hard)] + [sum(ok and _passes(row, objective) for row, ok in zip(rows, hard))
                               for objective in task["objectives"]]
        vectors[family] = tuple(Fraction(n, len(rows)) for n in counts)
        out["family_profiles"][family] = {
            "reviewed_unique_pairs": len(rows), "coverage_numerators": counts,
            "coverage_denominator": len(rows), "coverage_vector": [f"{n}/{len(rows)}" for n in counts],
            "support_ids": sorted(entries)}
    if fatal:
        return {**out, "disposition": "need_information", "reason": "incompatible_or_conflicting_evidence",
                "warnings": out["warnings"] + sorted(set(fatal))}
    if qualifiers:
        return {**out, "disposition": "stop", "reason": "observed_joint_success",
                "qualifying_ids": sorted(qualifiers)}
    if profile_errors:
        return {**out, "disposition": "need_information", "reason": "incomplete_or_unqualified_family_evidence",
                "warnings": out["warnings"] + sorted(set(profile_errors))}
    # This first implementation is a serial advisor. It neither submits parallel
    # work nor converts an ambiguous existing submission into a fresh attempt.
    if any(status in {"pending", "unknown"} for state in out["library_states"].values()
           for status in state["statuses"]):
        return {**out, "disposition": "need_information", "reason": "reconcile_existing_attempt"}
    # No source-supported novel exploration from repeating a tried CReM asset.
    attempted_content = {manifest[lid]["content_sha256"] for lid, state in out["library_states"].items()
                         if state["attempts"] > 0}
    attempted_normalized = {(manifest[lid]["normalization_policy_id"], manifest[lid]["normalized_input_set_sha256"])
                            for lid, state in out["library_states"].items() if state["attempts"] > 0}
    for lid, lib in manifest.items():
        out["library_states"][lid]["equivalent_content_already_attempted"] = lib["content_sha256"] in attempted_content
        out["library_states"][lid]["equivalent_normalized_input_already_attempted"] = (
            lib["normalization_policy_id"], lib["normalized_input_set_sha256"]) in attempted_normalized
    candidates = [lid for lid, lib in manifest.items()
                  if lib.get("approved") is True and lib.get("available_for_analysis") is True
                  and lib["capability_card_reviewed"] is True
                  and lib["context_id"] == task["context_id"]
                  and lib["family_definition_id"] == task["family_definition_id"]
                  and lib["normalization_policy_id"] == task["library_identity_policy_id"]
                  and lib["content_sha256"] not in attempted_content
                  and (lib["normalization_policy_id"], lib["normalized_input_set_sha256"]) not in attempted_normalized
                  and out["library_states"][lid]["attempts"] == 0]
    # Reuse the same admission/identity checks for reasoning advisers. This is
    # the allowed menu, not a claim all entries have equal scientific promise.
    out["eligible_library_ids"] = candidates
    if not candidates:
        return {**out, "disposition": "no_action", "reason": "approved_action_set_exhausted"}
    if strategy == "round_robin":
        return {**out, "disposition": "recommend", "library_id": candidates[0], "reason": "fixed_untried_order"}
    unknown = [lid for lid in candidates if manifest[lid]["target_family"] not in vectors]
    if unknown:
        return {**out, "disposition": "recommend", "library_id": unknown[0],
                "reason": "explicit_untried_family_exploration"}
    if not any(vectors[manifest[lid]["target_family"]][0] > 0 for lid in candidates):
        return {**out, "disposition": "need_information", "reason": "no_hard_feasible_matched_output_observed"}

    def dominates(a, b):
        return all(x >= y for x, y in zip(a, b)) and any(x > y for x, y in zip(a, b))

    front = [lid for lid in candidates if not any(
        dominates(vectors[manifest[other]["target_family"]], vectors[manifest[lid]["target_family"]])
        for other in candidates if other != lid)]
    chosen = front[0]  # Fixed manifest tie-break, not timing/recency.
    return {**out, "disposition": "recommend", "library_id": chosen,
            "asset_ref": manifest[chosen]["asset_ref"], "action_signature": action_signature(manifest[chosen]),
            "target_family": manifest[chosen]["target_family"], "coverage_front": front,
            "reason": "context_matched_family_coverage_hypothesis"}
