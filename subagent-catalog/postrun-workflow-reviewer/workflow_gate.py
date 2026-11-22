"""Build the workflow-review schema and screen advice without granting execution."""
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from packet_evidence import HEX, canonical, load, sha, validate_packet

TEXT = {"type": "string", "pattern": r"\S"}
ARTIFACT = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"}
BINDINGS = {"type": "object", "propertyNames": TEXT, "additionalProperties": ARTIFACT}
PARAMETERS = {"type": "object", "propertyNames": TEXT}


def closed(properties):
    return {"type": "object", "properties": properties, "required": sorted(properties),
            "additionalProperties": False}


def list_of(item, minimum=0):
    return {"type": "array", "items": item, "minItems": minimum, "uniqueItems": True}


WORKFLOW = closed({
    "task_evidence": TEXT, "evaluation_evidence": TEXT, "resource_evidence": TEXT,
    "external_inputs": list_of(ARTIFACT),
    "stages": list_of(closed({
        "id": TEXT, "engine": {"enum": ["boltzmann", "local"]}, "tool": TEXT,
        "status": {"enum": ["succeeded", "failed", "skipped", "unknown"]}, "result_evidence": TEXT,
        "parameters": PARAMETERS, "inputs": BINDINGS, "outputs": BINDINGS,
    }), 1),
})
PARAMETER = closed({
    "kind": {"const": "parameter"}, "stage": TEXT, "field": TEXT, "new": {}, "contract": TEXT,
})
REPLACEMENT = closed({
    "kind": {"const": "tool_replacement"}, "stage": TEXT, "new_tool": TEXT,
    "inputs": BINDINGS, "parameters": PARAMETERS, "outputs": BINDINGS, "compatibility": TEXT,
})
SCOPE = closed({
    "workflow_evidence_id": TEXT, "catalog": {"oneOf": [TEXT, {"type": "null"}]},
    "options": list_of({"oneOf": [PARAMETER, REPLACEMENT]}),
})
COMPATIBILITY = closed({
    "stage": TEXT, "old_tool": TEXT, "new_tool": TEXT, "inputs": BINDINGS, "outputs": BINDINGS,
    "sources": list_of(TEXT, 1), "assumptions": TEXT,
    "output_checks": {"type": "object", "propertyNames": ARTIFACT, "additionalProperties": TEXT},
})


def validate(schema, data):
    error = next(Draft202012Validator(schema).iter_errors(data), None)
    if error is not None:
        location = ".".join(str(part) for part in error.absolute_path)
        raise ValueError(f"Invalid {location or 'document'}: {error.message}")


def check_evidence(ids, paths):
    if set(ids) - paths.keys():
        raise ValueError("Workflow or option refers to unassigned evidence")


def workflow_graph(workflow, paths):
    producers = dict.fromkeys(workflow["external_inputs"])
    stages, parents = {}, {}
    check_evidence((workflow["task_evidence"], workflow["evaluation_evidence"],
                    workflow["resource_evidence"]), paths)
    for stage in workflow["stages"]:
        name = stage["id"]
        inputs = set(stage["inputs"].values())
        outputs = set(stage["outputs"].values())
        check_evidence([stage["result_evidence"]], paths)
        if name in stages or inputs - producers.keys() or outputs & producers.keys():
            raise ValueError("Duplicate stage/artifact or input without a preceding producer")
        if len(outputs) != len(stage["outputs"]) or stage["parameters"].keys() & stage["inputs"].keys():
            raise ValueError("Stage must bind each output distinctly and keep input fields separate from parameters")
        parents[name] = {producers[artifact] for artifact in inputs} - {None}
        stages[name] = stage
        producers.update(dict.fromkeys(outputs, name))
    return stages, parents


def rerun_stages(parents, stage):
    affected = set()
    for name, upstream in parents.items():
        if name == stage or affected & upstream:
            affected.add(name)
    return [name for name in parents if name in affected]


def catalog_from_scope(scope, paths):
    if scope["catalog"] is None:
        return None, []
    check_evidence([scope["catalog"]], paths)
    path = paths[scope["catalog"]]
    if path.name != "tool-contracts.v1.json":
        raise ValueError("Use the exact frozen Boltzmann tool catalog")
    required = [path, path.with_name("file-input-contracts.v1.json"), path.with_name("input-limits.v1.json")]
    ids_by_path = {value: key for key, value in paths.items()}
    if any(item not in ids_by_path for item in required):
        raise ValueError("Assign the matching native file contracts and input limits")
    from plugins.boltzmann.contracts import ContractStore

    return ContractStore(path.parent), [ids_by_path[item] for item in required]


def native_request(catalog, tool, inputs, parameters):
    if catalog is None:
        raise ValueError("Boltzmann advice requires the assigned native catalog")
    fields = catalog.tool(tool)["request_schema"]["properties"]
    file_fields = catalog.file_fields(tool)
    if inputs.keys() - file_fields.keys() or parameters.keys() - fields.keys() \
            or parameters.keys() & (inputs.keys() | file_fields.keys()):
        raise ValueError("Native request contains unsupported fields or misclassifies an artifact binding")
    # Logical artifact filenames stand in for refreshed storage receipts during admission.
    report = catalog.validate_payload(tool, inputs | parameters)
    if report.errors:
        raise ValueError(f"Native candidate violates the documented request: {report.errors}")


def parameter_change(option, stage, catalog, catalog_ids, paths):
    field, new, contract = option["field"], option["new"], option["contract"]
    check_evidence([contract], paths)
    if field not in stage["parameters"]:
        raise ValueError("A parameter edit must address a field frozen in the baseline")
    old = stage["parameters"][field]
    if type(old) is not type(new) or canonical(old) == canonical(new):
        raise ValueError("A parameter edit must change the value without changing its wire type")
    if stage["engine"] == "boltzmann":
        if not catalog_ids or contract != catalog_ids[0]:
            raise ValueError("Native parameter edits must cite the assigned native catalog")
        native_request(catalog, stage["tool"], stage["inputs"], stage["parameters"] | {field: new})
    else:
        documented = load(paths[contract])["stages"][stage["id"]]["settings"][field]
        if not isinstance(documented, list) or not {canonical(old), canonical(new)} <= set(map(canonical, documented)):
            raise ValueError("Local parameter edit is outside the frozen contract")
    citations = catalog_ids if stage["engine"] == "boltzmann" else [contract]
    return option | {"tool": stage["tool"], "old": old}, citations


def replacement_change(option, stage, catalog, catalog_ids, paths):
    tool, compatibility = option["new_tool"], option["compatibility"]
    if tool == stage["tool"]:
        raise ValueError("A replacement must select a different tool")
    check_evidence([compatibility], paths)
    mapping = load(paths[compatibility])
    validate(COMPATIBILITY, mapping)
    expected = {key: option[key] for key in ("stage", "new_tool", "inputs", "outputs")}
    if any(mapping[key] != value for key, value in expected.items()) or mapping["old_tool"] != stage["tool"]:
        raise ValueError("Replacement differs from its frozen compatibility record")
    check_evidence(mapping["sources"], paths)
    if sorted(option["inputs"].values()) != sorted(stage["inputs"].values()):
        raise ValueError("Replacement must use the same frozen input artifacts")
    if sorted(option["outputs"].values()) != sorted(stage["outputs"].values()):
        raise ValueError("Replacement must preserve the artifact outputs that downstream stages expect")
    if mapping["output_checks"].keys() != set(option["outputs"].values()):
        raise ValueError("Define downstream compatibility checks for each replacement output")
    native_request(catalog, tool, option["inputs"], option["parameters"])
    return option | {"old_tool": stage["tool"], "catalog": catalog_ids[0]}, [compatibility, *catalog_ids, *mapping["sources"]]


def prepare(packet_path, frozen_digest):
    if (not HEX.fullmatch(frozen_digest) or packet_path.is_symlink() or not packet_path.is_file()
            or sha(packet_path) != frozen_digest):
        raise ValueError("Packet digest differs from the frozen dispatch")
    packet = load(packet_path)
    paths = validate_packet(packet, packet_path.parent)
    check_evidence(["scope"], paths)
    scope = load(paths["scope"])
    validate(SCOPE, scope)
    workflow_id = scope["workflow_evidence_id"]
    check_evidence([workflow_id], paths)
    if sha(paths[workflow_id]) != packet["baseline_sha256"]:
        raise ValueError("Complete workflow snapshot differs from the frozen baseline")
    workflow = load(paths[workflow_id])
    validate(WORKFLOW, workflow)
    stages, parents = workflow_graph(workflow, paths)
    catalog, catalog_ids = catalog_from_scope(scope, paths)
    admitted = {}
    for option in scope["options"]:
        stage = stages.get(option["stage"])
        if stage is None or stage["status"] not in {"succeeded", "failed"}:
            raise ValueError("Only stages with a known completed attempt can have options")
        if option["kind"] == "parameter":
            change, citations = parameter_change(option, stage, catalog, catalog_ids, paths)
        else:
            change, citations = replacement_change(option, stage, catalog, catalog_ids, paths)
        key = canonical(change)
        if key in admitted:
            raise ValueError("Duplicate admitted workflow change")
        admitted[key] = (change, {stage["result_evidence"], workflow["evaluation_evidence"], *citations})
    if sha(packet_path) != frozen_digest:
        raise ValueError("Packet changed while preparing review")
    return packet, parents, admitted


def decision_schema(packet, admitted):
    common = {
        "case_id": {"const": packet["case_id"]}, "baseline_sha256": {"const": packet["baseline_sha256"]},
        "evidence": list_of({"enum": sorted(packet["evidence"])}, 1),
        "diagnosis": TEXT, "success_criterion": TEXT,
    }
    branches = [
        closed(common | {"decision": {"const": "retain"}, "reversal_criterion": TEXT}),
        closed(common | {"decision": {"const": "blocked"}, "missing_requirement": TEXT}),
    ]
    if admitted:
        branches.append(closed(common | {
            "decision": {"const": "propose"}, "change": {"enum": [row[0] for row in admitted.values()]},
            "fixed_conditions": TEXT, "expected_benefit": TEXT, "cost_and_risk": TEXT,
            "validation_plan": TEXT, "reversal_criterion": TEXT,
        }))
    return {"type": "object", "oneOf": branches}


def screen(decision, schema, admitted, parents):
    validate(schema, decision)
    rerun = []
    if decision["decision"] == "propose":
        option = admitted.get(canonical(decision["change"]))
        if option is None or not option[1] <= set(decision["evidence"]):
            raise ValueError("Proposal must match an exact typed option and cite its required evidence")
        rerun = rerun_stages(parents, decision["change"]["stage"])
    return {"decision": decision["decision"], "rerun_stages": rerun,
            "status": "scope_screened", "execution_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--packet-sha256", required=True, help="Exact digest frozen before dispatch")
    parser.add_argument("--decision", type=Path, help="Screen a response instead of emitting its schema")
    args = parser.parse_args()
    try:
        packet, parents, admitted = prepare(args.packet, args.packet_sha256)
        schema = decision_schema(packet, admitted)
        result = screen(load(args.decision), schema, admitted, parents) if args.decision else schema
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    if args.decision:
        result["packet_sha256"] = args.packet_sha256
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
