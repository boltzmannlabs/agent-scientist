#!/usr/bin/env python3
"""Computational selection record v1: which candidate ranked best, under which criteria, and why.

validate <record.json>        # structural + honesty checks; exit 0 required before reporting a selection
template                      # print a fillable template

The record captures best_under_contract ONLY: a computational preference under the frozen criteria. It never
establishes experimental validity; best_design stays null; limitations are mandatory.
"""
import argparse
import json
from pathlib import Path

REQUIRED_TOP = ["record_version", "basis", "ranked", "best_computational_candidate", "limitations"]
NOT_EXPERIMENTAL = "experimental"


def structural(rec):
    problems = []
    if not isinstance(rec, dict):
        return ["top level must be an object"]
    problems += [f"missing required field: {k}" for k in REQUIRED_TOP if k not in rec]
    if rec.get("record_version") != 1:
        problems.append("record_version must be 1")
    basis = rec.get("basis")
    if not isinstance(basis, dict):
        problems.append("basis must be an object")
    else:
        crit = basis.get("criteria")
        if not isinstance(crit, dict) or not crit:
            problems.append("basis.criteria (weights/gates/thresholds actually applied) is required")
        if not isinstance(basis.get("candidate_source"), str) or not basis["candidate_source"].strip():
            problems.append("basis.candidate_source (where the ranked candidates came from) is required")
        if not isinstance(basis.get("n_candidates"), int) or basis["n_candidates"] < 1:
            problems.append("basis.n_candidates must be a positive integer")
    ranked = rec.get("ranked")
    if not isinstance(ranked, list) or not ranked:
        problems.append("ranked must be a non-empty list")
    else:
        for i, row in enumerate(ranked):
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
                problems.append(f"ranked[{i}].id required")
            props = row.get("properties")
            if not isinstance(props, dict) or not props:
                problems.append(f"ranked[{i}].properties (per-property values) required")
    best = rec.get("best_computational_candidate")
    if not isinstance(best, dict):
        problems.append("best_computational_candidate must be an object")
    else:
        if not isinstance(best.get("id"), str) or not best["id"].strip():
            problems.append("best_computational_candidate.id required")
        attr = best.get("property_attribution")
        if not isinstance(attr, list) or not attr or any(not isinstance(a, str) or not a.strip() for a in attr):
            problems.append("best_computational_candidate.property_attribution must be a non-empty list of strings naming WHICH properties drove the top rank")
    lim = rec.get("limitations")
    if not isinstance(lim, list) or not lim:
        problems.append("limitations must be a non-empty list")
    elif not any(NOT_EXPERIMENTAL in str(l).lower() for l in lim):
        problems.append("limitations must state that this is NOT experimental validation and best_design remains null")
    # consistency: best must be the rank-1 id when ranks are present
    if isinstance(ranked, list) and ranked and isinstance(best, dict):
        r1 = ranked[0].get("id")
        if r1 and best.get("id") != r1:
            problems.append(f"best_computational_candidate.id ({best.get('id')}) != rank-1 id ({r1})")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["validate", "template"])
    ap.add_argument("record", nargs="?", type=Path)
    a = ap.parse_args()
    if a.cmd == "template":
        print(json.dumps({
            "record_version": 1,
            "basis": {"candidate_source": "<run/artifact the candidates came from>",
                      "criteria": {"weights": {"<property>": 0.0}, "hard_gates": ["<gate>"], "thresholds": {"<name>": 0.0}},
                      "n_candidates": 0},
            "ranked": [{"rank": 1, "id": "<candidate-id>", "composite": 0.0,
                        "properties": {"<property>": 0.0}, "gate_pass": True}],
            "best_computational_candidate": {"id": "<rank-1 id>",
                                             "margins": {"vs_runner_up_composite": 0.0},
                                             "property_attribution": ["<property> <delta> vs runner-up", "..."]},
            "sensitivity": "<one-line weight/threshold sensitivity note>",
            "limitations": ["Computational preference under the stated contract only; NOT experimental validation; best_design remains null"]
        }, indent=1))
        return 0
    if a.record is None:
        print(json.dumps({"status": "INVALID", "error": "record path required"}))
        return 1
    try:
        rec = json.loads(a.record.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}))
        return 2
    problems = structural(rec)
    print(json.dumps({"status": "PASS" if not problems else "FAIL", "problems": problems,
                      "note": "best_under_contract only; never an experimental claim"}, indent=1))
    return 0 if not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
