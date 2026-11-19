#!/usr/bin/env python3
"""Deterministic RNA routing: classify a request against the packaged routing table.

Usage: route_request.py --text "..." | --file request.json
Request JSON: {"mode": "ROUTE"|"SETUP"|"AUDIT", "text": "...", ...}
Output JSON: routed leaf, matched mechanisms, ambiguity or NOT_COVERED verdict, missing inputs.
Exit 0 routed/ask; 2 invalid request. No delegation, network or science happens here.
"""
import argparse
import json
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1]
TABLE = json.loads((P / "references/routing-table.json").read_text(encoding="utf-8-sig"))


def _hits(text, terms):
    found = []
    for term in terms:
        pattern = re.escape(term.lower())
        if re.search(r"(?<![a-z])" + pattern + r"(?![a-z])", text) or term.lower() in text:
            found.append(term)
    return found


def route(text):
    t = (text or "").lower()
    if not t.strip():
        return {"status": "INVALID_REQUEST", "notes": ["empty request text"]}
    scores = {}
    for r in TABLE["routes"]:
        hits = _hits(t, [m for m in r["mechanism"]])
        if hits:
            scores[r["leaf"]] = hits
    # ambiguity: silencing language without any mechanism hit
    silencing = bool(_hits(t, ["silence", "silencing", "knock down", "knockdown"]))
    mechanism_named = bool(scores)
    if silencing and not mechanism_named:
        for a in TABLE["ambiguous"]:
            if a["pattern"][0].split(" without")[0].split()[0] in t or silencing:
                return {"status": "ASK", "question": a["resolve"],
                        "matched": [], "notes": ["mechanism must be named: siRNA/RNAi vs CRISPRi vs knockout"]}
    if not scores:
        for nc in TABLE["not_covered"]:
            key = nc.split(" as the deliverable")[0].split("/")[0].strip().lower()
            if key and key in t:
                return {"status": "NOT_COVERED", "matched_class": nc,
                        "notes": ["report the gap and the closest future leaf; do not substitute a covered leaf"]}
        return {"status": "NOT_COVERED",
                "notes": ["no routing-table mechanism matched; report the gap"]}
    if len(scores) > 1:
        # multiple modality families: discovery/execution verbs refine design routes
        design = {k: v for k, v in scores.items() if k.startswith("application-aware-")}
        meta = {k: v for k, v in scores.items() if k.startswith("rna-model-")}
        if design and meta:
            # capability verbs dominate design mentions in the same sentence
            meta_terms = {"find a model", "find an open-source", "search for models", "missing capability",
                          "weights available", "pretrained weights", "modelintegration spec",
                          "evaluate candidates", "model discovery", "install the model",
                          "integrate the model", "run the spec", "execute inference",
                          "checkpoint verification", "execution report"}
            if any(h in meta_terms for hits in meta.values() for h in hits):
                scores = meta
            else:
                scores = design
        if len(scores) > 1:
            return {"status": "ASK", "question": "Multiple modality families matched: " + ", ".join(sorted(scores)),
                    "matched": {k: v for k, v in scores.items()},
                    "notes": ["ask the user to name one mechanism/modality"]}
    leaf, hits = next(iter(scores.items()))
    rule = TABLE.get("capability_gap_rule", "")
    return {"status": "ROUTED", "leaf": leaf, "matched": hits,
            "capability_gap_rule": rule,
            "notes": ["deterministic table match; the orchestrator assembles the brief and emits the directive"]}


def preflight(req):
    base = {"delegation_started": False, "scientific_execution": False, "authorization_granted": False}
    if not isinstance(req, dict):
        return {**base, "status": "INVALID_REQUEST", "notes": ["JSON object required"]}
    mode = req.get("mode", "ROUTE")
    if mode not in {"ROUTE", "SETUP", "AUDIT"}:
        return {**base, "status": "INVALID_REQUEST", "notes": ["mode must be ROUTE, SETUP or AUDIT"]}
    if mode == "SETUP":
        missing = [f for f in ["target_leaves", "output_root"] if not (req.get(f) if isinstance(req.get(f), (str, list)) else None)]
        if missing:
            return {**base, "status": "NEEDS_INPUT", "missing_inputs": missing,
                    "notes": ["dependency setup requires the target leaf set and an output root"]}
        return {**base, "status": "SETUP_PLAN_READY",
                "notes": ["run scripts/dependency_plan.py --leaf <name> (plan) or --verify (host probe)"]}
    if mode == "AUDIT":
        return {**base, "status": "AUDIT_ONLY",
                "notes": ["inspect registry, routing table and dependency readiness; no delegation"]}
    out = route(req.get("text", "") if isinstance(req.get("text"), str) else "")
    if isinstance(req.get("text"), list) or "text" not in req:
        out = {"status": "INVALID_REQUEST", "notes": ["text (string) is required for ROUTE"]}
    return {**base, **out}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--text")
    ap.add_argument("--file", type=Path)
    a = ap.parse_args()
    if a.file:
        try:
            req = json.loads(a.file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, UnicodeError):
            print(json.dumps({"status": "INVALID_REQUEST", "notes": ["unreadable or malformed JSON"]}))
            return 2
    elif a.text is not None:
        req = {"mode": "ROUTE", "text": a.text}
    else:
        req = {}
    out = preflight(req if a.file else req)
    print(json.dumps(out, indent=2))
    return 2 if out.get("status") == "INVALID_REQUEST" else 0


if __name__ == "__main__":
    raise SystemExit(main())
