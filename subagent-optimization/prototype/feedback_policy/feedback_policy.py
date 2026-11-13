"""Offline proposed policy. Trusted host facts in; recommendation out. No I/O.

This module does not validate chemistry, qualify services, grant authorization,
reserve resources or execute requests. See README.md for the host boundary.
"""
from copy import deepcopy
import hashlib
import json
import math
import random
import statistics


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _count(value):
    return type(value) is int and value >= 0


def _key(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_key(value).encode()).hexdigest()


def _property(config):
    # Old frozen/artificial Solubility configurations remain replayable.
    return config.get("property_metric", "solubility")


def _models(config, route):
    return config.get("route_objective_models", {}).get(route, config["objective_models"])


def validate_config(config):
    require(type(config.get("seed")) is int, "Explicit exploration seed required")
    require(_count(config.get("panel_size")) and config["panel_size"] > 0,
            "Positive panel size required")
    references = config.get("reference_roles")
    require(isinstance(references, dict) and references
            and all(isinstance(i, str) and i and role in {"lead", "control"}
                    for i, role in references.items()), "Frozen reference identities/roles required")
    constraints = config.get("constraints", {})
    prop = _property(config)
    require(prop in {"solubility", "pampa"}, "Unsupported declared property metric")
    require(set(constraints) == {prop, "qed", "crippen_logp"},
            "This prototype requires the three declared constraints")
    for name, rule in constraints.items():
        require(isinstance(rule.get("method"), str) and rule["method"]
                and isinstance(rule.get("unit"), str) and rule["unit"],
                "Method and unit required: " + name)
        require(any(k in rule for k in ("min", "max")), "Constraint needs a bound")
        require(all(_finite(rule[k]) for k in ("min", "max") if k in rule),
                "Finite constraint bounds required")
        require(rule.get("min", -math.inf) <= rule.get("max", math.inf),
                "Reversed bounds")
    quality = config.get("quality", {})
    require(quality.get("metric") == "vina" and quality.get("direction") == "min"
            and quality.get("method") and quality.get("unit"),
            "One explicit lower-is-better Vina evaluator required")
    priorities = config.get("constraint_priorities", [])
    require(isinstance(priorities, list) and len(set(priorities)) == len(priorities)
            and set(priorities) <= set(constraints), "Invalid constraint priorities")
    overrides = config.get("route_objective_models", {})
    require(isinstance(overrides, dict) and set(overrides) <= {"crem", "graph_ga"},
            "Unsupported route model configuration")
    for models in [config.get("objective_models", {}), *overrides.values()]:
        require(isinstance(models, dict) and set(models) <= {"global_models", "custom_models"}
                and any(models.values()), "Frozen property-model selection required")
        for kind, selections in models.items():
            require(isinstance(selections, list), "Model selections must be lists")
            identity_field = "name" if kind == "global_models" else "id"
            for model in selections:
                require(isinstance(model, dict)
                        and set(model) == {identity_field, "min_threshold", "max_threshold"}
                        and isinstance(model[identity_field], str) and model[identity_field],
                        "Model selection requires documented identity and bounds")
                require(all(isinstance(model[k], str) or _finite(model[k])
                            for k in ("min_threshold", "max_threshold")), "Invalid model bounds")
    if prop == "pampa":
        output_kind = config.get("pampa_output_kind", "class_score")
        require(output_kind in {"class_label", "class_score"}, "PAMPA output kind required")
        if output_kind == "class_label":
            require(constraints["pampa"].get("min") == 1 and constraints["pampa"].get("max") == 1,
                    "PAMPA label eligibility requires exactly class 1")
            require(config.get("pampa_score_boundary") == .5,
                    "Native class-label mode retains the separate 0.5 score boundary")
        score_boundary = config.get("pampa_score_boundary", constraints["pampa"].get("min"))
        for model in _models(config, "graph_ga").get("global_models", []):
            if model["name"] == "PAMPA":
                try:
                    lo, hi = float(model["min_threshold"]), float(model["max_threshold"])
                except ValueError as exc:
                    raise InputError("Numeric PAMPA GA reward boundary required") from exc
                require(_finite(lo) and _finite(hi) and lo < hi
                        and hi == score_boundary,
                        "PAMPA GA step must match the declared score boundary, not a label value")
    # Meaning/scale of these supplied selections is qualified by the host, not here.


def _rows(rows, config):
    """Collapse duplicate observations, retaining control/lead recovery roles."""
    grouped = {}
    for row in rows:
        identity = row.get("identity")
        require(isinstance(identity, str) and identity, "Host molecular identity required")
        require(row.get("role") in {"lead", "control", "generated"}, "Candidate role required")
        require(type(row.get("valid")) is bool, "Explicit host validity required")
        require(isinstance(row.get("smiles"), str) and row["smiles"], "Host SMILES required")
        require(isinstance(row.get("measurements"), dict), "Measurement records required")
        core = {k: deepcopy(row[k]) for k in ("identity", "valid", "smiles", "measurements")}
        if identity in grouped:
            require(grouped[identity]["core"] == core,
                    "Conflicting observations for identity: " + identity)
            grouped[identity]["roles"].add(row["role"])
        else:
            grouped[identity] = {"core": core, "roles": {row["role"]}}
        if identity in config["reference_roles"]:
            grouped[identity]["roles"].add(config["reference_roles"][identity])
    return grouped


def _value(row, name, config):
    rule = config["quality"] if name == "vina" else config["constraints"][name]
    measurement = row["measurements"].get(name, {})
    if not isinstance(measurement, dict):
        return None
    value = measurement.get("value")
    if (measurement.get("status") != "ok" or not _finite(value)
            or measurement.get("method") != rule["method"]
            or measurement.get("unit") != rule["unit"]):
        return None
    if name == "pampa":
        kind = config.get("pampa_output_kind", "class_score")
        if measurement.get("output_kind", "class_score") != kind:
            return None
        if kind == "class_label" and value not in (0, 1):
            return None
        if not 0 <= value <= 1:
            return None
    return value


def _violations(row, config):
    values = {name: _value(row, name, config) for name in config["constraints"]}
    if any(value is None for value in values.values()):
        return None
    return {name: max(rule.get("min", -math.inf) - values[name],
                      values[name] - rule.get("max", math.inf), 0)
            for name, rule in config["constraints"].items()}


def _eligible(row, config):
    violation = _violations(row, config)
    return row["valid"] and violation is not None and not any(violation.values())


def _new(entry):
    return entry["roles"] == {"generated"}


def _parent_order(grouped, config):
    available = {i: e["core"] for i, e in grouped.items()
                 if e["core"]["valid"] and "control" not in e["roles"]}
    eligible = [i for i, row in available.items()
                if _eligible(row, config) and _value(row, "vina", config) is not None]
    if eligible:
        return sorted(eligible, key=lambda i: (_value(available[i], "vina", config), i))
    # A feasible parent with missing docking requires assessment, not replacement
    # by a known-infeasible parent merely because its values are complete.
    if any(_eligible(row, config) for row in available.values()):
        return []
    vectors = {i: _violations(row, config) for i, row in available.items()}
    vectors = {i: v for i, v in vectors.items() if v is not None}
    front = [i for i, a in vectors.items() if not any(
        all(b[k] <= a[k] for k in a) and any(b[k] < a[k] for k in a)
        for j, b in vectors.items() if j != i)]
    priorities = config.get("constraint_priorities", [])
    # Never sum violations measured in different units.
    front.sort()
    random.Random(config["seed"]).shuffle(front)
    if priorities:
        front.sort(key=lambda i: tuple(vectors[i][k] for k in priorities))
    return front


def action_key(card):
    """Scientific identity ignores display IDs and textual rationale aliases."""
    payload = deepcopy(card.get("payload"))
    if card.get("route") == "crem" and isinstance(payload, dict):
        # Different upload handles for the same admitted material are aliases.
        payload.pop("library_path", None)
    return _digest({"route": card.get("route"), "parent_identity": card.get("parent_identity"),
                    "payload": payload, "library_identity": card.get("library_identity")})


def _card_error(card, grouped, config, resources, history):
    route = card.get("route")
    if route not in {"crem", "graph_ga", "assess"}:
        return "unsupported_route"
    if card.get("qualified") is not True:
        return "host_capability_unqualified"
    if not all(isinstance(card.get(k), str) and card[k]
               for k in ("profile_id", "hypothesis", "counterevidence")):
        return "missing_action_rationale_or_profile"
    if not isinstance(card.get("evidence_refs"), list) or not card["evidence_refs"]:
        return "missing_supporting_evidence"
    targets = card.get("targets", [])
    if not isinstance(targets, list) or not targets or not set(targets) <= {
            _property(config), "qed", "crippen_logp", "docking", "missing_evidence"}:
        return "invalid_targets"
    allocation = card.get("search_allocation")
    if not _count(allocation) or allocation < 1:
        return "invalid_assessment_allocation"
    if allocation > resources["search_remaining"]:
        return "insufficient_search_allowance"
    if route != "assess" and resources["generation_remaining"] < 1:
        return "generation_allowance_exhausted"
    if action_key(card) in history:
        repeat = card.get("repeat")
        if repeat not in {"replication", "stochastic_resampling"}:
            return "repeat_requires_specific_question"
        if repeat == "stochastic_resampling" and card.get("stochasticity_verified") is not True:
            return "stochastic_behavior_unverified"
    payload = card.get("payload")
    if not isinstance(payload, dict):
        return "invalid_payload"
    if route == "assess":
        if set(payload) != {"identities"} or not isinstance(payload["identities"], list):
            return "invalid_assessment_request"
        ids = payload["identities"]
        if (not ids or len(set(ids)) != len(ids) or len(ids) > allocation
                or not all(i in grouped and grouped[i]["core"]["valid"] for i in ids)):
            return "unknown_or_unassessable_identity"
        return None
    parent = card.get("parent_identity")
    if parent not in grouped or not grouped[parent]["core"]["valid"]:
        return "invalid_parent"
    if card.get("objective_qualified") is not True:
        return "hosted_objective_unresolved"
    fields = {"global_models", "custom_models"}
    required = {"ref_mol", "library_path"} if route == "crem" else {"smiles", "n_mols", "n_steps"}
    if not required <= set(payload) or not set(payload) <= required | fields:
        return "unsupported_public_fields"
    if {k: payload[k] for k in fields if k in payload} != _models(config, route):
        return "objective_selection_mismatch"
    smiles_field = "ref_mol" if route == "crem" else "smiles"
    if payload[smiles_field] != grouped[parent]["core"]["smiles"]:
        return "parent_payload_mismatch"
    if route == "crem":
        if not card.get("library_identity") or not isinstance(payload["library_path"], str) or not payload["library_path"]:
            return "missing_admitted_library"
    elif not all(_count(payload[k]) and payload[k] > 0 for k in ("n_mols", "n_steps")):
        return "invalid_ga_profile"
    return None


def decide(snapshot, cards, config):
    """Recommend an admitted action; execution requires a separate host adapter."""
    validate_config(config)
    require(snapshot.get("state") in {"active", "closed", "frozen", "completed"}, "State required")
    base = {"policy_version": "feedback-v2-offline-1", "execution": "not_performed",
            "scientific_benefit": "not_assessed", "chosen": None,
            "alternatives": [], "rejected": [], "internal_compute": "unknown"}

    def result(disposition, reason, **extra):
        return {**base, "disposition": disposition, "reason": reason, **extra}

    if snapshot["state"] != "active":
        return result("STOP", "task_terminal")
    jobs = snapshot.get("jobs", [])
    require(all(j.get("id") and j.get("status") in {
        "pending", "running", "acceptance_unknown", "complete", "failed"} for j in jobs),
        "Job identity/status required")
    waiting = sorted(j["id"] for j in jobs if j["status"] in {
        "pending", "running", "acceptance_unknown"})
    if waiting:
        return result("WAIT", "reconcile_existing_work", job_ids=waiting)
    resources = snapshot.get("resources", {})
    require(all(_count(resources.get(k)) for k in (
        "generation_remaining", "search_remaining", "final_remaining")),
        "Finite nonnegative observable allowances required for offline selection")
    if resources["final_remaining"] < config["panel_size"]:
        return result("STOP", "insufficient_final_reserve")
    if snapshot.get("stopping_condition_met") is True:
        return result("STOP", "declared_stopping_condition_met")
    grouped = _rows(snapshot.get("candidates", []), config)
    history = snapshot.get("attempted_action_keys", [])
    require(isinstance(history, list) and all(isinstance(k, str) for k in history),
            "Action history keys required")
    eligible_new = sorted(i for i, entry in grouped.items() if _new(entry)
                          and _eligible(entry["core"], config))
    prop = _property(config)
    property_fail, other_fail, unresolved = [], set(), []
    for identity, entry in sorted(grouped.items()):
        row = entry["core"]
        if "control" in entry["roles"] or not row["valid"]:
            continue
        violation = _violations(row, config)
        if violation is None or _value(row, "vina", config) is None:
            unresolved.append(identity)
        if violation is not None:
            failed = {k for k, value in violation.items() if value > 0}
            if failed == {prop}:
                property_fail.append(identity)
            other_fail.update(failed - {prop})
    parents = _parent_order(grouped, config)
    admissible = {}
    for card in cards:
        error = _card_error(card, grouped, config, resources, history)
        if error is None and card["route"] != "assess" and card["parent_identity"] not in parents:
            error = "parent_missing_required_evidence_or_dominated"
        if error:
            base["rejected"].append({"action_key": action_key(card), "reason": error})
            continue
        key = action_key(card)
        # Aliases must agree on scientific targets and admission facts.
        if key in admissible:
            previous = admissible[key]
            require(set(previous["targets"]) == set(card["targets"]), "Conflicting action alias targets")
        if key not in admissible or _key(card) < _key(admissible[key]):
            admissible[key] = deepcopy(card)
    base["rejected"].sort(key=lambda r: (r["action_key"], r["reason"]))
    available = list(admissible.values())
    observations = {"eligible_new": eligible_new, prop + "_only_failures": property_fail,
                    "unresolved_identities": unresolved, "admissible_parents": parents}
    if not available:
        return result("NEEDS_EVIDENCE" if unresolved else "STOP", "no_admissible_action",
                      observations=observations)
    reason = "explicit_exploration"
    preferred = []
    if not parents and unresolved:
        preferred = [a for a in available if a["route"] == "assess"
                     and set(a["payload"]["identities"]) & set(unresolved)]
        if preferred:
            reason = "resolve_parent_evidence"
    if not preferred and len(eligible_new) < config["panel_size"] and property_fail:
        preferred = [a for a in available if a["route"] == "graph_ga" and prop in a["targets"]]
        if preferred:
            reason = "measured_" + prop + "_deficit"
    if not preferred and any(_eligible(e["core"], config) for e in grouped.values()
                             if "control" not in e["roles"]):
        preferred = [a for a in available if a["route"] == "crem" and "docking" in a["targets"]]
        if preferred:
            reason = "eligible_parent_docking_hypothesis"
    if not preferred and other_fail:
        preferred = [a for a in available if set(a["targets"]) & other_fail]
        if preferred:
            reason = "other_measured_constraint_gap"
    candidates = preferred or available
    # Route first: aliases/larger card menus cannot inflate one optimizer's weight.
    rng = random.Random(config["seed"])
    route = rng.choice(sorted({a["route"] for a in candidates}))
    candidates = [a for a in candidates if a["route"] == route]
    if route != "assess":
        rank = min(parents.index(a["parent_identity"]) for a in candidates)
        candidates = [a for a in candidates if parents.index(a["parent_identity"]) == rank]
    chosen = rng.choice(sorted(candidates, key=action_key))
    chosen_key = action_key(chosen)
    base["alternatives"] = [{"action_key": key, "route": a["route"],
                              "hypothesis": a["hypothesis"]}
                             for key, a in sorted(admissible.items()) if key != chosen_key]
    return result("RECOMMEND", reason, chosen={**chosen, "action_key": chosen_key},
                  observations=observations,
                  rationale={"goal": reason, "evidence": chosen["evidence_refs"],
                             "hypothesis": chosen["hypothesis"],
                             "counterevidence": chosen["counterevidence"]})


def select_panel(rows, config):
    """Shared proposed selection, not an on-disk immutable commitment."""
    validate_config(config)
    grouped = _rows(rows, config)
    eligible = [i for i, e in grouped.items() if _new(e) and _eligible(e["core"], config)
                and _value(e["core"], "vina", config) is not None]
    eligible.sort(key=lambda i: (_value(grouped[i]["core"], "vina", config), i))
    ids = eligible[:config["panel_size"]]
    slots = ids + [None] * (config["panel_size"] - len(ids))
    return {"identities": slots, "content_sha256": _digest(slots),
            "status": "FILLED" if None not in slots else "UNFILLED"}


def summarize_final(panel, final_rows, config):
    """Read committed slots only; never fill a failure from other candidates."""
    validate_config(config)
    ids = panel["identities"]
    require(len(ids) == config["panel_size"] and panel["content_sha256"] == _digest(ids),
            "Panel changed or wrong size")
    present = [i for i in ids if i is not None]
    require(len(set(present)) == len(present), "Duplicate panel identity")
    grouped = _rows(final_rows, config)
    successful, qualifying, scores = [], [], []
    for identity in ids:
        if identity not in grouped:
            continue
        entry = grouped[identity]
        row = entry["core"]
        score = _value(row, "vina", config)
        if _new(entry) and row["valid"] and score is not None and _violations(row, config) is not None:
            successful.append(identity)
            scores.append(score)
            if _eligible(row, config):
                qualifying.append(identity)
    complete = len(successful) == config["panel_size"]
    return {"status": "COMPLETE" if complete else "INCOMPLETE_EVALUATION",
            "successful_slots": len(successful), "qualifying_slots": len(qualifying),
            "mean_native_vina": statistics.mean(scores) if complete else None,
            "all_eligible": complete and len(qualifying) == config["panel_size"]}


def assessment_subset(identities, allowance, seed):
    """Common prospective sampling, with no access to unseen docking outcomes."""
    require(_count(allowance) and type(seed) is int, "Nonnegative allowance and seed required")
    unique = sorted(set(identities))
    require(all(isinstance(i, str) and i for i in unique), "Host identities required")
    return sorted(random.Random(seed).sample(unique, min(allowance, len(unique))))


def classify_batch(previous_rows, returned_rows, config, *, objective_active,
                   intended_change_observed):
    """Non-exclusive descriptive feedback, never an automatic next submission."""
    validate_config(config)
    require(objective_active is None or type(objective_active) is bool,
            "Objective status must be true, false or unknown")
    require(intended_change_observed is None or type(intended_change_observed) is bool,
            "Intended change status must be true, false or unknown")
    before, after = _rows(previous_rows, config), _rows(returned_rows, config)
    new = sorted(set(after) - set(before))
    combined = deepcopy(before)
    conflicts = []
    for identity, entry in after.items():
        if identity in before and entry["core"] != before[identity]["core"]:
            # Partial duplicates must not erase retained observations. Repeated
            # samples need a host-approved aggregation rule before replacement.
            conflicts.append(identity)
            combined[identity]["roles"].update(entry["roles"])
            continue
        combined[identity] = deepcopy(entry)
        if identity in before:
            combined[identity]["roles"].update(before[identity]["roles"])
    def eligible_scores(group):
        return {i: _value(e["core"], "vina", config) for i, e in group.items()
                if _new(e) and _eligible(e["core"], config)
                and _value(e["core"], "vina", config) is not None}
    old_scores = eligible_scores(before)
    retained_scores = eligible_scores(combined)
    gain = min(config["panel_size"], len(retained_scores)) > min(config["panel_size"], len(old_scores))
    def pool_mean(scores):
        return (statistics.mean(sorted(scores.values())[:config["panel_size"]])
                if len(scores) >= config["panel_size"] else None)
    old_mean, retained_mean = pool_mean(old_scores), pool_mean(retained_scores)
    better = old_mean is not None and retained_mean is not None and retained_mean < old_mean
    unresolved = bool(conflicts) or objective_active is not True or intended_change_observed is None or any(
        not e["core"]["valid"] or _violations(e["core"], config) is None
        or _value(e["core"], "vina", config) is None for e in after.values())
    unchanged = not new and all(i in before and before[i]["core"] == e["core"]
                                for i, e in after.items())
    progress = gain or better
    return {"progress": progress,
            "coverage_progress": gain, "retained_pool_quality_progress": better,
            "retained_pool_mean_before": old_mean, "retained_pool_mean_after": retained_mean,
            "counterevidence": intended_change_observed is False or bool(new and not progress and not unresolved),
            "no_new_information": unchanged,
            "unresolved_evidence": unresolved, "new_identities": new,
            "unresolved_observation_conflicts": sorted(conflicts),
            "interpretation": "descriptive_search_feedback_not_scientific_validation"}
