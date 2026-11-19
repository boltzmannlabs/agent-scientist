#!/usr/bin/env python3
"""Inert metadata routing for rna-model-discovery: no network, search, evaluation or model claim."""
import argparse
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
MODES = {"SETUP", "AUDIT", "DISCOVER", "EVALUATE", "SPEC"}


def present(x):
    return isinstance(x, str) and bool(x.strip())


def preflight(r):
    def result(status, missing=(), notes=()):
        return {"status": status, "missing_inputs": list(missing), "notes": list(notes),
                "scientific_execution": False, "network_used": False, "authorization_granted": False}

    if not isinstance(r, dict):
        return result("INVALID_REQUEST", notes=["JSON object required"])
    mode = r.get("mode")
    if not isinstance(mode, str) or mode not in MODES:
        return result("INVALID_REQUEST", notes=["Exact uppercase mode required: " + "/".join(sorted(MODES))])
    if mode in {"SETUP", "AUDIT"}:
        return result("SETUP_FIRST" if mode == "SETUP" else "AUDIT_ONLY",
                      notes=["Inspect approvals, connectors and registry state; no search or evaluation"])
    if mode in {"DISCOVER", "EVALUATE", "SPEC"}:
        missing = [f for f in ["task_description", "output_root"] if not present(r.get(f))]
        if mode == "DISCOVER":
            if not present(r.get("capability_gap")):
                missing.append("capability_gap")
            if not present(r.get("search_authorization")):
                missing.append("search_authorization")
            if r.get("registry_path") is not None and not present(r.get("registry_path")):
                missing.append("registry_path")
        if mode == "EVALUATE":
            if not present(r.get("candidate_manifest")):
                missing.append("candidate_manifest")
        if mode == "SPEC":
            for f in ["selected_candidate", "evidence_manifest"]:
                if not present(r.get(f)):
                    missing.append(f)
        if missing:
            return result("NEEDS_INPUT", missing,
                          ["Discovery requires explicit task, gap and parent-owned approvals before any search"])
        return result("METADATA_COMPLETE_REQUIRES_PARENT_AND_CONNECTOR_CHECKS", [],
                      ["Network search still requires the parent's egress authorization at run time"])
    return result("INVALID_REQUEST")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("request", type=Path)
    a = p.parse_args()
    try:
        r = json.loads(a.request.read_text())
        out = preflight(r)
    except (OSError, ValueError, UnicodeError):
        out = {"status": "INVALID_REQUEST", "missing_inputs": [], "notes": ["Unreadable or malformed JSON"],
               "scientific_execution": False, "network_used": False, "authorization_granted": False}
    print(json.dumps(out, indent=2))
    return 2 if out["status"] in {"INVALID_REQUEST"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
