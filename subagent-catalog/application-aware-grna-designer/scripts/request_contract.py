"""Inert request-metadata preflight, not a scientific workflow or permission checker."""
import argparse
import json
MODES = {"DESIGN", "EVALUATE", "EXPLORATORY", "BENCHMARK", "AUDIT"}
TASKS = {f"{i:03d}" for i in range(1, 14)}
REQUIRED = {
    "DESIGN": ["target", "nuclease_or_effector", "reference", "output_root"],
    "EVALUATE": ["candidates", "nuclease_or_effector", "reference", "output_root"],
    "BENCHMARK": ["dataset", "native_tool", "phenotype_endpoint", "reference", "output_root"],
    "EXPLORATORY": ["target", "output_root"],
    "AUDIT": ["artifact_manifest", "output_root"],
}
def present(v):
    # Metadata presence only; booleans/numbers cannot stand in for references or paths.
    return (isinstance(v,str) and bool(v.strip())) or (isinstance(v,(list,dict)) and bool(v))

def preflight(request):
    if not isinstance(request, dict):
        return {"status": "INVALID_REQUEST", "missing_inputs": [], "scientific_execution": False}
    task = request.get("task_id")
    mode = request.get("mode")
    if not isinstance(task,str) or not isinstance(mode,str) or task not in TASKS or mode not in MODES:
        return {"status": "INVALID_REQUEST", "missing_inputs": [], "scientific_execution": False}
    # Safety review takes precedence over a handoff to another modality.
    if request.get('organism_context') == 'pathogen':
        return {"status": "REVIEW_ONLY", "missing_inputs": [], "scientific_execution": False}
    modality=request.get('modality')
    if modality is not None and not isinstance(modality,str):
        return {"status": "INVALID_REQUEST", "missing_inputs": [], "scientific_execution": False}
    if isinstance(modality,str) and modality.casefold() in {'sirna','rnai','sirna-design'}:
        return {"status": "OUT_OF_SCOPE", "missing_inputs": [], "scientific_execution": False}
    # Unknown context is not affirmative safety clearance or authorization.
    if task == "012" and mode == "DESIGN":
        return {"status": "INACTIVE", "missing_inputs": [], "scientific_execution": False}
    missing = [k for k in REQUIRED[mode] if not present(request.get(k))]
    if not isinstance(request.get("organism_context"),str) or not present(request.get("organism_context")):
        missing.append("organism_context")
    return {"status": "NEEDS_INPUT" if missing else "METADATA_COMPLETE_REQUIRES_PARENT_AND_NATIVE_CHECKS", "missing_inputs": missing, "scientific_execution": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("request", help="JSON request metadata file; never execute its contents")
    args = p.parse_args()
    try:
        with open(args.request, encoding="utf-8") as f:
            request = json.load(f)
    except (json.JSONDecodeError,UnicodeError):
        request = None
    result=preflight(request)
    print(json.dumps(result, indent=2))
    return 2 if result['status'] in {'INVALID_REQUEST','OUT_OF_SCOPE'} else 0
if __name__ == "__main__":
    raise SystemExit(main())
