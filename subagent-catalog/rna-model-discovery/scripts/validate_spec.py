#!/usr/bin/env python3
"""Structural ModelIntegrationSpec v1 validation (stdlib only; schema is the contract document).

Usage: validate_spec.py <spec.json> [--schema <schema.json>]
Exit 0 valid / 2 invalid. Uses jsonschema when importable for strict Draft 2020-12 checks;
otherwise the built-in structural checker (same required fields and enums).
"""
import argparse
import json
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1]
SCHEMA = P / "references/model-integration-spec.schema.json"

DOMAINS = ["mrna", "sirna", "aso", "grna", "circrna", "rna_structure", "rna_protein", "rna_ligand", "general_rna"]
WEIGHTS = ["WEIGHTS_PUBLIC", "WEIGHTS_RESTRICTED", "NO_WEIGHTS", "WEIGHTS_VERIFIED_LOCAL"]
TOP_REQUIRED = ["spec_version", "task_definition", "selected_model", "weights_availability",
                "alternatives_considered", "input_schema", "output_schema", "dependencies",
                "runtime_requirements", "official_inference_instructions", "known_limitations", "selection_rationale"]


def structural(spec):
    problems = []
    if not isinstance(spec, dict):
        return ["top level must be an object"]
    missing = [k for k in TOP_REQUIRED if k not in spec]
    problems += [f"missing required field: {k}" for k in missing]
    extra = sorted(set(spec) - set(TOP_REQUIRED) - {"provenance", "benchmark_evidence"})
    problems += [f"unknown field (additionalProperties false): {k}" for k in extra]
    if spec.get("spec_version") != 1:
        problems.append("spec_version must be 1")
    td = spec.get("task_definition")
    if isinstance(td, dict):
        for k in ["capability", "biological_task", "domain"]:
            if not isinstance(td.get(k), str) or not td[k].strip():
                problems.append(f"task_definition.{k} must be a non-empty string")
        if td.get("domain") not in DOMAINS:
            problems.append(f"task_definition.domain must be one of {DOMAINS}")
    elif "task_definition" in spec:
        problems.append("task_definition must be an object")
    sm = spec.get("selected_model")
    if isinstance(sm, dict):
        for k in ["name", "repository_url", "commit", "license"]:
            if not isinstance(sm.get(k), str) or not sm[k].strip():
                problems.append(f"selected_model.{k} must be a non-empty string")
        if isinstance(sm.get("repository_url"), str) and not re.match(r"^(?:https?://|file\x3a//|/|[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,})", sm["repository_url"]):
            problems.append("selected_model.repository_url must be an http(s)/file URL, absolute path or scheme-less host")
        pubs = sm.get("publication_references")
        if not isinstance(pubs, list) or not pubs:
            problems.append("selected_model.publication_references must be a non-empty list")
        ck = sm.get("checkpoint")
        if ck is not None and (not isinstance(ck, dict) or not isinstance(ck.get("urls"), list)):
            problems.append("selected_model.checkpoint.urls must be a list")
    elif "selected_model" in spec:
        problems.append("selected_model must be an object")
    if spec.get("weights_availability") not in WEIGHTS:
        problems.append(f"weights_availability must be one of {WEIGHTS}")
    if spec.get("weights_availability") == "NO_WEIGHTS" and isinstance(sm, dict) and sm.get("checkpoint"):
        problems.append("NO_WEIGHTS selected_model must not carry checkpoint URLs")
    alts = spec.get("alternatives_considered")
    if isinstance(alts, list):
        for i, alt in enumerate(alts):
            if not isinstance(alt, dict) or not all(isinstance(alt.get(k), str) and alt[k].strip()
                                                    for k in ["name", "repository_url", "weights_availability", "verdict"]):
                problems.append(f"alternatives_considered[{i}] malformed")
    elif "alternatives_considered" in spec:
        problems.append("alternatives_considered must be a list")
    for k in ["input_schema", "output_schema"]:
        if k in spec and not isinstance(spec[k], dict):
            problems.append(f"{k} must be an object")
    if "official_inference_instructions" in spec and (not isinstance(spec.get("official_inference_instructions"), str) or not spec["official_inference_instructions"].strip()):
        problems.append("official_inference_instructions must be a non-empty string")
    kl = spec.get("known_limitations")
    if not isinstance(kl, list) or not kl:
        problems.append("known_limitations must be a non-empty list")
    if "selection_rationale" in spec and (not isinstance(spec.get("selection_rationale"), str) or not spec["selection_rationale"].strip()):
        problems.append("selection_rationale must be a non-empty string")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--schema", type=Path, default=SCHEMA)
    a = ap.parse_args()
    try:
        spec = json.loads(a.spec.read_text(encoding="utf-8"))
        json.loads(a.schema.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "INVALID", "validator": "io", "error": str(exc)}))
        return 2
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
        schema = json.loads(a.schema.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(spec), key=lambda e: list(e.path))
        problems = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
        validator = "jsonschema-draft2020-12"
    except ImportError:
        problems = structural(spec)
        validator = "builtin-structural"
    ok = not problems
    print(json.dumps({"status": "PASS" if ok else "FAIL", "validator": validator,
                      "spec_version": spec.get("spec_version") if isinstance(spec, dict) else None,
                      "problems": problems,
                      "note": "Structural validation only; never evidence of model quality or readiness"},
                     indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
