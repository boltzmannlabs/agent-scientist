"""Host-mediated scientific steps for one durable specialist assignment.

The specialist supplies an identity-bound decision. This controller validates it,
runs the existing connector through admission, and processes results. No extra
main-agent scientific reasoning, HTTP client, provider fallback or retry loop.
"""

from copy import deepcopy
import json
import re
from pathlib import Path
from workflow.admission import AdmissionGate, _links
from workflow.native_episode import validate_outcome
from workflow.session import digest


def _gate(session, dispatcher):
    return AdmissionGate(session, warning_validator=dispatcher.validate)


def _call(gate, dispatcher, name, args):
    return gate(
        tool_name=name,
        args=deepcopy(args),
        next_call=lambda checked: dispatcher(name, checked),
    )


def advance(session, assignment, native_result, dispatcher):
    """An explicit host-mediated action request is required; blocked advice cannot execute."""
    if (
        native_result.get("validation_status") != "passed"
        or native_result.get("mode") != "host_mediated"
    ):
        raise ValueError("Actual validated host-mediated episode required")
    return _advance(session, assignment, native_result, dispatcher)


def advance_delegated(session, assignment, wire_outcome, alias_manifest, dispatcher, *, provenance):
    """Accept a decision delivered by the owning SDK's specialist-bound tool.

    The SDK bridge checks actual caller scope before this process is invoked.
    This path records direct-tool provenance; it does not invent an isolated
    runner's inference, usage, completion or delegation receipt.
    """
    if (not isinstance(provenance, dict)
            or provenance.get("specialist") != "smallmol-investigation"
            or not isinstance(provenance.get("revision"), str)
            or not provenance["revision"].strip()
            or provenance.get("transport") != "native-specialist-tool"
            or not isinstance(provenance.get("home"), str)
            or not Path(provenance["home"]).is_absolute()):
        raise ValueError("Owning native-specialist tool provenance required")
    if assignment.get("capability_contract", {}).get("execution_mode") != "host_mediated":
        raise ValueError("Direct delegation requires a host-mediated assignment")
    from workflow.identifiers import present_assignment, expand_outcome, wire_outcome_schema
    schema = json.loads((Path(__file__).parents[1] / "specialist/optimization-v1/outcome.schema.json").read_text())
    wire, expected_manifest = present_assignment(assignment)
    if alias_manifest != expected_manifest:
        raise ValueError("Stored identifier presentation no longer matches this assignment")
    checked = validate_outcome(wire, wire_outcome, wire_outcome_schema(schema))
    canonical = validate_outcome(assignment, expand_outcome(checked, alias_manifest), schema)
    decision = {"outcome": canonical, "wire_outcome": checked,
                "identifier_alias_manifest": alias_manifest}
    result = _advance(session, assignment, decision, dispatcher)
    result["decision_provenance"] = deepcopy(provenance)
    return result


def _advance(session, assignment, native_result, dispatcher):
    """Shared semantic checks/admission for already qualified transports."""
    if assignment.get("input_digest") != digest(
        {k: v for k, v in assignment.items() if k != "input_digest"}
    ):
        raise ValueError("Assignment input changed")
    if (
        assignment["assignment_id"] != session.assignment_id
        or assignment["campaign_id"] != session.campaign_id
        or assignment["task_digest"] != session.spec["task_digest"]
        or assignment["objective_config_digest"] != digest(session.spec["objective"])
        or assignment["evidence_snapshot_digest"] != digest(session.report())
    ):
        raise ValueError(
            "Decision is stale or belongs to another scientific assignment"
        )
    schema = json.loads(
        (
            Path(__file__).parents[1] / "specialist/optimization-v1/outcome.schema.json"
        ).read_text()
    )
    outcome = validate_outcome(assignment, native_result["outcome"], schema)
    rationale = outcome["rationale"]
    manifest = native_result.get("identifier_alias_manifest")
    if manifest:
        from workflow.identifiers import expand_outcome

        if expand_outcome(native_result["wire_outcome"], manifest) != outcome:
            raise ValueError("Wire and canonical outcomes disagree")
        # Keep stable references in history; display aliases may change later.
        names = manifest["alias_to_canonical"]
        rationale = re.sub(
            r"\b[MFEA][0-9]{3,}\b", lambda m: names.get(m.group(), m.group()), rationale
        )
    if outcome["status"] == "completed":
        return {
            "phase": "completed",
            "freeze": session.finish(
                outcome["final_candidate_ids"], outcome["stop_reason"]
            ),
        }
    if outcome["status"] == "stopped":
        return {
            "phase": "stopped",
            "freeze": session.finish([], outcome["stop_reason"]),
        }
    if outcome["status"] != "action_requested":
        return {
            "phase": outcome["status"],
            "scientific_submissions": 0,
            "reason": outcome["stop_reason"],
        }
    action = outcome["chosen_action"]
    view = session.search_view()
    match = next(
        (
            a
            for a in view["eligible_actions"]
            if a["action_key"] == action["action_key"]
            and a["parent_candidate_id"] == action["parent_id"]
            and a["library_id"] == action["library_id"]
        ),
        None,
    )
    if match is None:
        raise ValueError("Requested scientific action no longer eligible")
    report = session.report()
    observations = {o["id"] for o in report["observations"]}
    evidence = set(outcome["evidence_ids"]) & observations
    cited_candidates = set(outcome["evidence_ids"]) & {
        c["id"] for c in report["candidates"]
    }
    evidence.update(
        o["id"] for o in report["observations"] if o["candidate_id"] in cited_candidates
    )
    session.store.dispatch(
        "decision",
        session.campaign_id,
        {
            "id": "decision-" + digest([assignment["input_digest"], outcome]),
            "question": "Which parent/library investigation should follow the observed batch?",
            "outcome": "inconclusive",
            "evidence_ids": sorted(evidence),
            "next_action": action["action_key"],
            "rationale": rationale
            + " This is a search hypothesis, not measured improvement.",
        },
    )
    parent = next(c for c in report["candidates"] if c["id"] == action["parent_id"])
    library = next(
        l for l in session.spec["libraries"] if l["id"] == action["library_id"]
    )
    payload = {
        **session.spec["objective"]["generation_parameters"],
        "ref_mol": parent["representation"],
    }
    gate = _gate(session, dispatcher)
    uploaded = _call(
        gate,
        dispatcher,
        "boltzmann_upload",
        {
            "job_name": "Fragment_Based_Optimization",
            "input_field": "library_path",
            "local_path": library["csv_path"],
            "experiment_data": payload,
        },
    )
    if uploaded.get("status") != "uploaded" or uploaded.get("error"):
        return {"phase": "upload_unfinished", "receipt": uploaded}
    submitted = _call(
        gate, dispatcher, "boltzmann_submit", uploaded["workflow_next_submit"]
    )
    return {
        "phase": "waiting"
        if submitted.get("status") == "accepted" and not submitted.get("error")
        else "submission_unresolved",
        "receipt": submitted,
        "action_key": action["action_key"],
    }


def collect(session, dispatcher):
    """One read-only observation pass; pending jobs do not consume another model call."""
    session.reconcile_usage()
    gate = _gate(session, dispatcher)
    outcomes = []
    for original in session.attempts():
        key = original["action_key"]
        state = original["state"]
        if state in {"complete", "failed", "upload_blocked"}:
            continue
        if state != "downloaded":
            job_id = original.get("submit", {}).get("doc_id")
            if not job_id:
                outcomes.append(
                    {"action_key": key, "phase": "needs_reconciliation", "state": state}
                )
                continue
            receipt = _call(
                gate,
                dispatcher,
                "boltzmann_status",
                {"job_name": "Fragment_Based_Optimization", "doc_id": job_id},
            )
            original = next(a for a in session.attempts() if a["action_key"] == key)
            state = original["state"]
            if state not in {"results_ready", "downloaded"}:
                outcomes.append(
                    {
                        "action_key": key,
                        "phase": "waiting" if state == "accepted" else state,
                    }
                )
                continue
        if state == "results_ready":
            links = list(dict.fromkeys(_links(original.get("monitor", {}))))
            if len(links) != 1:
                outcomes.append(
                    {"action_key": key, "phase": "artifact_mapping_required"}
                )
                continue
            folder = str(Path(session.spec["artifact_directory"]) / key)
            _call(
                gate,
                dispatcher,
                "boltzmann_download",
                {"download_url": links[0], "output_folder": folder},
            )
            original = next(a for a in session.attempts() if a["action_key"] == key)
            state = original["state"]
        if state == "downloaded":
            result = session.complete_download(key)
            outcomes.append(
                {"action_key": key, "phase": "observations_ready", "assessment": result}
            )
        else:
            outcomes.append({"action_key": key, "phase": state})
    return outcomes
