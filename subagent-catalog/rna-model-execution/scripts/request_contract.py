#!/usr/bin/env python3
"""Inert metadata routing for rna-model-execution: no install, download or inference."""
import argparse
import json
from pathlib import Path

MODES = {"SETUP", "AUDIT", "INSTALL", "RUN", "VALIDATE", "REGISTER"}


def present(x):
    return isinstance(x, str) and bool(x.strip())


def preflight(r):
    def result(status, missing=(), notes=()):
        return {"status": status, "missing_inputs": list(missing), "notes": list(notes),
                "scientific_execution": False, "installation_executed": False, "authorization_granted": False}

    if not isinstance(r, dict):
        return result("INVALID_REQUEST", notes=["JSON object required"])
    mode = r.get("mode")
    if not isinstance(mode, str) or mode not in MODES:
        return result("INVALID_REQUEST", notes=["Exact uppercase mode required: " + "/".join(sorted(MODES))])
    if mode in {"SETUP", "AUDIT"}:
        return result("SETUP_FIRST" if mode == "SETUP" else "AUDIT_ONLY",
                      notes=["Inspect approvals, destinations, registry and checkpoint state; no installation"])
    if mode == "INSTALL":
        missing = [f for f in ["model_integration_spec", "approved_destination", "egress_authorization", "output_root"] if not present(r.get(f))]
        if missing:
            return result("NEEDS_INPUT", missing,
                          ["Isolated installation requires the spec, a fresh approved prefix and explicit egress approval"])
        return result("METADATA_COMPLETE_REQUIRES_PARENT_AND_NATIVE_CHECKS", [],
                      ["Installation commands still execute only under the parent's approved plan"])
    if mode in {"RUN", "VALIDATE"}:
        missing = [f for f in ["environment_receipt", "input_manifest", "output_root"] if not present(r.get(f))]
        if mode == "RUN" and not present(r.get("model_integration_spec")):
            missing.append("model_integration_spec")
        if missing:
            return result("NEEDS_INPUT", missing)
        return result("METADATA_COMPLETE_REQUIRES_PARENT_AND_NATIVE_CHECKS")
    if mode == "REGISTER":
        missing = [f for f in ["registry_path", "entry_id", "target_state", "execution_report"] if not present(r.get(f))]
        if missing:
            return result("NEEDS_INPUT", missing, ["Registry transitions require the execution evidence"])
        return result("METADATA_COMPLETE_REQUIRES_PARENT_AND_NATIVE_CHECKS")
    return result("INVALID_REQUEST")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("request", type=Path)
    a = p.parse_args()
    try:
        r = json.loads(a.request.read_text(encoding="utf-8-sig"))
        out = preflight(r)
    except (OSError, ValueError, UnicodeError):
        out = {"status": "INVALID_REQUEST", "missing_inputs": [], "notes": ["Unreadable or malformed JSON"],
               "scientific_execution": False, "installation_executed": False, "authorization_granted": False}
    print(json.dumps(out, indent=2))
    return 2 if out["status"] in {"INVALID_REQUEST"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
