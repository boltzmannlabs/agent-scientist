"""Deterministic evidence views and a simple search control for investigator v1.

These helpers do not predict properties, generate molecules, submit jobs, claim
causal edit effects or estimate uncertainty. Parent identities and local metrics
are checked against the ORIGINAL reference. Reported Lipophilicity remains an
externally supplied provider score; callers own artifact/provenance validation.
Use the qualified RDKit scoring interpreter, not an SDK interpreter without RDKit.
"""
from copy import deepcopy
import hashlib
import json
import math

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import QED, rdFingerprintGenerator

from pilot.assessment import _identity
from prototype.library_audit.audit import _parser


METRICS = ("lipophilicity", "qed", "lead_similarity")
METHOD = "original-reference-parent-library-search-v1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _objective(value):
    required = ("target_min", "target_max", "qed_min_exclusive", "similarity_min_exclusive")
    if not isinstance(value, dict) or any(not _finite(value.get(k)) for k in required):
        raise ValueError("Explicit finite original-task thresholds required")
    if (value["target_min"] > value["target_max"]
            or not 0 <= value["qed_min_exclusive"] <= 1
            or not 0 <= value["similarity_min_exclusive"] < 1):
        raise ValueError("Invalid target interval or descriptor bounds")
    # Bind ALL supplied objective metadata, including model/units/version facts
    # and unknowns. This helper does not authenticate their scientific meaning.
    _digest(value)
    return deepcopy(value)


def _graph(record, id_key):
    if (not isinstance(record, dict) or any(not _text(record.get(k)) for k in (id_key, "form_id"))
            or not isinstance(record.get("representation"), str)):
        raise ValueError("Candidate ID, exact form ID and representation required")
    return _identity(record["representation"])


def action_identity(parent, library, objective, *, original_reference=None, tool_parameters=None, tool_version=None):
    """Identify an exact parent/library/objective action, independent of aliases.

    ``parent`` uses candidate_id (or id), form_id and representation. A library
    uses id and lowercase content_sha256. Unknown backend version remains None;
    it does not establish determinism or backend reproducibility. Supply the
    original_reference to bind the task anchor; build_search_view always does.
    """
    key = "candidate_id" if "candidate_id" in parent else "id"
    graph, status, _ = _graph(parent, key)
    if status:
        raise ValueError("Action parent lacks a qualified exact molecular identity")
    sha = library.get("content_sha256") if isinstance(library, dict) else None
    if (not isinstance(library, dict) or not _text(library.get("id"))
            or not isinstance(sha, str) or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)):
        raise ValueError("Library ID and exact lowercase SHA-256 required")
    if tool_parameters is not None and not isinstance(tool_parameters, dict):
        raise ValueError("Tool parameters must be an object or None")
    if tool_version is not None and not _text(tool_version):
        raise ValueError("Tool version must be a nonempty string or None")
    original = None
    if original_reference is not None:
        original, status, _ = _graph(original_reference, "id")
        if status:
            raise ValueError("Original reference identity is not qualified")
    return _digest({"method": METHOD, "parent_exact_graph": graph, "original_reference_exact_graph": original,
                    "library_content_sha256": sha, "objective": _objective(objective),
                    "tool_parameters": tool_parameters, "tool_version": tool_version})


def constraint_view(values, objective):
    """Return separate-unit gaps and explicit strict-boundary violations.

    A zero numeric gap at an exclusive boundary is still a violation. Gaps are
    diagnostic only; there is no weighted sum or replacement for joint success.
    """
    task = _objective(objective)
    if not isinstance(values, dict) or any(not _finite(values.get(k)) for k in METRICS):
        raise ValueError("Finite compatible property/descriptor values required")
    score, qed, similarity = (values[k] for k in METRICS)
    if not 0 <= qed <= 1 or not 0 <= similarity <= 1:
        raise ValueError("QED and molecular similarity must be between zero and one")
    passes = {"lipophilicity": task["target_min"] <= score <= task["target_max"],
              "qed": qed > task["qed_min_exclusive"],
              "lead_similarity": similarity > task["similarity_min_exclusive"]}
    gaps = {"lipophilicity": max(task["target_min"] - score, 0, score - task["target_max"]),
            "qed": max(task["qed_min_exclusive"] - qed, 0),
            "lead_similarity": max(task["similarity_min_exclusive"] - similarity, 0)}
    return {"passes": passes, "gaps": gaps, "all_constraints_satisfied": all(passes.values())}


def _dominates(left, right):
    # Preserve strict boundaries and useful QED/similarity margins after passing
    # them. Property-interval scores have no preference once inside the interval.
    # This is a partial order, not an addition of unlike-unit measurements.
    def vector(row):
        return [(not row["constraints"]["passes"][k], row["constraints"]["gaps"][k],
                 -row["values"][k] if k != "lipophilicity" else 0) for k in METRICS]
    a, b = vector(left), vector(right)
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def _priority(row):
    # Transparent simple control: prefer QED-qualified parents, then approach the
    # property interval, then higher QED/similarity. All parents already satisfy
    # the structural admission rule. No learned or calibrated utility is claimed.
    return (not row["constraints"]["passes"]["qed"],
            row["constraints"]["gaps"]["lipophilicity"],
            -row["values"]["qed"], -row["values"]["lead_similarity"], row["candidate_id"])


def build_search_view(candidates, *, reference, objective, libraries, actions=(),
                      tool_parameters=None, tool_version=None, representative_count=3):
    """Build a complete candidate view and a deterministic parent/library control.

    Candidate input: candidate_id, form_id, representation, values.lipophilicity;
    status and property_prediction_conflict are honored. QED/similarity are
    recomputed locally and never reanchored to a selected new parent. Include the
    reference as a candidate with its actual provider score to make it a parent.

    Every actions entry denotes a previous scientific attempt, including unknown
    or failed attempts, and needs action_key (action_id is also accepted). Planned, unsent options are not
    attempts. They all block automatic repetition; explicit stochastic replicates
    require a separate prospective protocol rather than a retry flag here.
    """
    task = _objective(objective)
    if not isinstance(candidates, list) or not isinstance(libraries, list):
        raise ValueError("Candidate and library lists required")
    if type(representative_count) is not int or representative_count < 0:
        raise ValueError("Nonnegative integer representative count required")
    original, status, _ = _graph(reference, "id")
    if status:
        raise ValueError("Original reference identity is not qualified")
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2)
    original_fp = generator.GetSparseCountFingerprint(Chem.MolFromSmiles(original, _parser()))
    attempted = set()
    retained_actions = []
    for action in actions:
        if not isinstance(action, dict) or not _text(action.get("action_key", action.get("action_id"))):
            raise ValueError("Each attempted action requires its action_key")
        if "action_key" in action and "action_id" in action and action["action_key"] != action["action_id"]:
            raise ValueError("Conflicting action identities")
        _digest(action)
        attempted.add(action.get("action_key", action.get("action_id")))
        retained_actions.append(deepcopy(action))
    normalized_libraries, library_ids, library_hashes = [], {}, set()
    for library in libraries:
        action_identity(reference, library, task, original_reference=reference,
                        tool_parameters=tool_parameters, tool_version=tool_version)
        lid, sha = library["id"], library["content_sha256"]
        if lid in library_ids and library_ids[lid] != sha:
            raise ValueError("One library ID refers to conflicting contents")
        library_ids[lid] = sha
    for library in sorted(libraries, key=lambda item: item["id"]):
        if library["content_sha256"] not in library_hashes:
            normalized_libraries.append(deepcopy(library)); library_hashes.add(library["content_sha256"])

    rows, groups, fingerprints = [], {}, {}
    id_graphs, form_graphs = {reference["id"]: original}, {reference["form_id"]: original}
    for supplied in candidates:
        graph, invalid, reason = _graph(supplied, "candidate_id")
        row = {"candidate_id": supplied["candidate_id"], "form_id": supplied["form_id"],
               "representation": supplied["representation"], "status": invalid or "completed",
               "reason": reason, "is_reference": graph == original if graph else False,
               "parent_admissible": False, "qualified_candidate": False}
        rows.append(row)
        if invalid:
            continue
        for identity, mapping in ((row["candidate_id"], id_graphs), (row["form_id"], form_graphs)):
            if identity in mapping and mapping[identity] != graph:
                raise ValueError("A candidate/form identifier refers to different molecular graphs")
            mapping[identity] = graph
        row["canonical_form"] = graph
        supplied_values = supplied.get("values", {})
        score = supplied_values.get("lipophilicity") if isinstance(supplied_values, dict) else None
        if (supplied.get("status", "completed") != "completed"
                or supplied.get("property_prediction_conflict") or not _finite(score)):
            row.update(status="unresolved", reason="Missing, unresolved or conflicting provider property evidence")
        else:
            row["reported_lipophilicity"] = score
        groups.setdefault(graph, []).append(row)

    unique_rows = []
    for graph, aliases in groups.items():
        scores = {r["reported_lipophilicity"] for r in aliases if "reported_lipophilicity" in r}
        unresolved = any(r["status"] != "completed" for r in aliases)
        if len(scores) != 1 or unresolved:
            for row in aliases:
                row.update(status="unresolved", reason="Exact-form evidence missing or conflicting across records")
            continue
        mol = Chem.MolFromSmiles(graph, _parser())
        fp = generator.GetSparseCountFingerprint(mol); fingerprints[graph] = fp
        qed_mol = Chem.MolFromSmiles(reference["representation"], _parser()) if graph == original else mol
        values = {"lipophilicity": next(iter(scores)), "qed": QED.qed(qed_mol),
                  "lead_similarity": DataStructs.TanimotoSimilarity(fp, original_fp)}
        constraints = constraint_view(values, task)
        for row in aliases:
            row.update(values=deepcopy(values), constraints=deepcopy(constraints),
                       parent_admissible=bool(graph == original or constraints["passes"]["lead_similarity"]),
                       qualified_candidate=bool(graph != original and constraints["all_constraints_satisfied"]))
        representative = min(aliases, key=lambda r: (r["candidate_id"] != reference["id"], r["candidate_id"]))
        representative["alias_candidate_ids"] = sorted({r["candidate_id"] for r in aliases})
        unique_rows.append(representative)

    parents = [r for r in unique_rows if r["parent_admissible"]]
    frontier = [r for r in parents if not any(_dominates(other, r) for other in parents)]
    ranked_parents = sorted(frontier, key=_priority) + sorted([r for r in parents if r not in frontier], key=_priority)
    options = []
    for parent in ranked_parents:
        for library in normalized_libraries:
            identity = action_identity(parent, library, task, original_reference=reference,
                                       tool_parameters=tool_parameters, tool_version=tool_version)
            if identity not in attempted:
                options.append({"action_key": identity, "action_id": identity, "parent_candidate_id": parent["candidate_id"],
                                "parent_form_id": parent["form_id"], "parent_representation": parent["representation"],
                                "library_id": library["id"], "library_content_sha256": library["content_sha256"]})
    diversity = []
    remaining = list(ranked_parents)
    while remaining and len(diversity) < representative_count:
        if not diversity:
            chosen = remaining[0]
        else:
            chosen = min(remaining, key=lambda row: (
                -min(1 - DataStructs.TanimotoSimilarity(fingerprints[row["canonical_form"]], fingerprints[other["canonical_form"]])
                     for other in diversity), _priority(row)))
        diversity.append(chosen); remaining.remove(chosen)
    feasible = sorted(r["candidate_id"] for r in unique_rows if r["qualified_candidate"])
    if feasible:
        baseline = {"disposition": "stop", "reason": "objective_achieved", "action": None}
    elif options:
        baseline = {"disposition": "recommend", "reason": "simple_qed_then_property_gap_control",
                    "action": deepcopy(options[0])}
    elif parents:
        baseline = {"disposition": "stop", "reason": "no_remaining_admissible_action", "action": None}
    else:
        baseline = {"disposition": "need_information", "reason": "no_parent_with_compatible_evidence", "action": None}
    return {"method": METHOD, "rdkit_version": rdBase.rdkitVersion,
            "reference": deepcopy(reference), "objective": task, "rows": rows,
            "unique_completed_forms": len(unique_rows), "qualified_candidate_ids": feasible,
            "pareto_parent_ids": [r["candidate_id"] for r in sorted(frontier, key=_priority)],
            "diversity_representative_ids": [r["candidate_id"] for r in diversity],
            "eligible_actions": options, "attempted_actions": retained_actions, "baseline": baseline,
            "limitations": ["Provider score provenance, units and model revision must be qualified by the caller",
                            "Pareto gaps are task diagnostics, not a weighted reward or a success substitute",
                            "Molecular fingerprint diversity is not novelty or target-specific utility",
                            "Parent selection permits QED tradeoffs but always enforces original-reference similarity",
                            "No internal backend oracle-work estimate or calibrated uncertainty"]}
