#!/usr/bin/env python3
"""Structural ExecutionReport v1 validation (stdlib core; jsonschema used when importable)."""
import argparse
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
SCHEMA = P / "references/execution-report.schema.json"

TOP = ["report_version", "model_identity", "installation_status", "checkpoint_verification",
       "inference_status", "registry_update", "runtime", "hardware", "logs", "output_artifacts",
       "validation_results", "known_limitations"]
OPTIONAL = {"spec_reference"}
INSTALL_ST = {"NOT_RUN", "BLOCKED", "IN_PROGRESS", "COMPLETED", "FAILED"}
CKPT_ST = {"NOT_APPLICABLE", "NOT_RUN", "BLOCKED", "VERIFIED", "MISMATCH", "MISSING"}
INFER_ST = {"NOT_RUN", "BLOCKED", "COMPLETED", "PARTIAL", "FAILED"}
REG_ST = {"DISCOVERED", "EVIDENCE_REVIEWED", "WEIGHTS_AVAILABLE", "INSTALLED",
          "EXECUTION_TESTED", "BENCHMARK_VALIDATED", "PRODUCTION_APPROVED", "UNCHANGED"}


def structural(rep):
    problems = []
    if not isinstance(rep, dict):
        return ["top level must be an object"]
    problems += [f"missing required field: {k}" for k in TOP if k not in rep]
    problems += [f"unknown field (additionalProperties false): {k}"
                 for k in sorted(set(rep) - set(TOP) - OPTIONAL)]
    if rep.get("report_version") != 1:
        problems.append("report_version must be 1")
    mi = rep.get("model_identity")
    if not isinstance(mi, dict) or any(not isinstance(mi.get(k), str) or not mi[k].strip()
                                       for k in ["name", "repository", "commit"]):
        problems.append("model_identity requires name, repository and commit")
    ins = rep.get("installation_status")
    if isinstance(ins, dict):
        if ins.get("status") not in INSTALL_ST:
            problems.append(f"installation_status.status must be one of {sorted(INSTALL_ST)}")
        if not isinstance(ins.get("environment_path"), str):
            problems.append("installation_status.environment_path is required (may be 'NOT_CREATED')")
    else:
        problems.append("installation_status must be an object")
    ck = rep.get("checkpoint_verification")
    if isinstance(ck, dict):
        if ck.get("status") not in CKPT_ST:
            problems.append(f"checkpoint_verification.status must be one of {sorted(CKPT_ST)}")
    else:
        problems.append("checkpoint_verification must be an object")
    inf = rep.get("inference_status")
    if isinstance(inf, dict):
        if inf.get("status") not in INFER_ST:
            problems.append(f"inference_status.status must be one of {sorted(INFER_ST)}")
        for k in ["successful_records", "failed_records"]:
            if not isinstance(inf.get(k), int) or inf[k] < 0:
                problems.append(f"inference_status.{k} must be a non-negative integer")
        if inf.get("status") == "COMPLETED" and inf.get("successful_records", 0) == 0:
            problems.append("COMPLETED inference must report at least one successful record")
    else:
        problems.append("inference_status must be an object")
    ru = rep.get("registry_update")
    if isinstance(ru, dict):
        if ru.get("state_reached") not in REG_ST:
            problems.append(f"registry_update.state_reached must be one of {sorted(REG_ST)}")
        for k in ["registry_path", "entry_id"]:
            if not isinstance(ru.get(k), str) or not ru[k].strip():
                problems.append(f"registry_update.{k} is required")
    else:
        problems.append("registry_update must be an object")
    for k in ["logs", "output_artifacts"]:
        if not isinstance(rep.get(k), list):
            problems.append(f"{k} must be a list")
    vr = rep.get("validation_results")
    if isinstance(vr, list):
        for i, v in enumerate(vr):
            if not isinstance(v, dict) or v.get("outcome") not in {"PASS", "FAIL", "NOT_RUN"}:
                problems.append(f"validation_results[{i}] malformed")
    else:
        problems.append("validation_results must be a list")
    if not isinstance(rep.get("known_limitations"), list) or not rep["known_limitations"]:
        problems.append("known_limitations must be a non-empty list")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", type=Path)
    ap.add_argument("--schema", type=Path, default=SCHEMA)
    a = ap.parse_args()
    try:
        rep = json.loads(a.report.read_text(encoding="utf-8"))
        json.loads(a.schema.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "INVALID", "validator": "io", "error": str(exc)}))
        return 2
    try:
        from jsonschema import Draft202012Validator
        schema = json.loads(a.schema.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(rep), key=lambda e: list(e.path))
        problems = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
        validator = "jsonschema-draft2020-12"
    except ImportError:
        problems = structural(rep)
        validator = "builtin-structural"
    ok = not problems
    print(json.dumps({"status": "PASS" if ok else "FAIL", "validator": validator, "problems": problems,
                      "note": "Structural validation only; mechanical evidence, never biological validity"},
                     indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
