#!/usr/bin/env python3
"""Shared RNA model/tool registry CLI (stdlib only). Parent-owned registry file.

States form a strict adjacent-forward ladder:
  DISCOVERED -> EVIDENCE_REVIEWED -> WEIGHTS_AVAILABLE -> INSTALLED
            -> EXECUTION_TESTED -> BENCHMARK_VALIDATED -> PRODUCTION_APPROVED

Skipping states forward is refused without --force (recorded in state_history).
Backward transitions are always refused; re-verification is a new evidence note.

Commands:
  init <registry.json>
  add <registry.json> --id ID --domain D --task T [--task T...] --repo URL
      [--limit L] [--evidence E] [--spec-path P]
  show <registry.json> [ID]
  transition <registry.json> ID STATE [--note N] [--evidence E] [--force]
  validate <registry.json>

POLICY NOTE (parent-issued, 2026-11-19): for parent-supplied LOCAL fixture capabilities, the parent may define
WEIGHTS_AVAILABLE as "available to this system" (artifact parent-supplied and checksum-verified; public
availability unverified and documented in known_limitations). Adjacent transitions still apply; quote the
parent clarification in the transition evidence note.

Exit codes: 0 ok, 2 invalid usage/state/data.
"""
import argparse
import datetime
import json
from pathlib import Path

STATES = [
    "DISCOVERED", "EVIDENCE_REVIEWED", "WEIGHTS_AVAILABLE", "INSTALLED",
    "EXECUTION_TESTED", "BENCHMARK_VALIDATED", "PRODUCTION_APPROVED",
]
DOMAINS = ["mrna", "sirna", "aso", "grna", "circrna", "rna_structure",
           "rna_protein", "rna_ligand", "general_rna"]
READER_STATES = {"DISCOVERED", "EVIDENCE_REVIEWED", "WEIGHTS_AVAILABLE"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fail(msg):
    print(json.dumps({"status": "INVALID", "error": msg}))
    raise SystemExit(2)


def load(path):
    p = Path(path)
    if not p.is_file():
        fail(f"registry not found: {p} (run init first; the registry is parent-owned)")
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        fail(f"unreadable registry: {exc}")
    if not isinstance(doc, dict) or doc.get("registry_version") != 1 or not isinstance(doc.get("entries"), dict):
        fail("registry must be an object with registry_version 1 and entries")
    return p, doc


def structural_check(entry):
    import re
    req = ["id", "biological_domain", "supported_tasks", "repository", "state", "state_history", "last_verified", "known_limitations"]
    missing = [k for k in req if k not in entry]
    if missing:
        return f"missing fields: {', '.join(missing)}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", str(entry["id"])):
        return "id must match [a-z0-9][a-z0-9._-]*"
    if entry["biological_domain"] not in DOMAINS:
        return f"biological_domain must be one of {DOMAINS}"
    if not isinstance(entry["supported_tasks"], list) or not entry["supported_tasks"]:
        return "supported_tasks must be a non-empty list"
    if not isinstance(entry["known_limitations"], list) or not entry["known_limitations"]:
        return "known_limitations must be a non-empty list (an entry without limitations is not honest)"
    if entry["state"] not in STATES:
        return f"state must be one of {STATES}"
    hist = entry["state_history"]
    if not isinstance(hist, list) or not hist or hist[0].get("state") != "DISCOVERED":
        return "state_history must start at DISCOVERED"
    for i, step in enumerate(hist):
        if step.get("state") not in STATES or "at" not in step or "by" not in step:
            return f"state_history[{i}] malformed"
    # History must be an adjacent-forward walk (force steps carry note 'forced').
    for a, b in zip(hist, hist[1:]):
        ia, ib = STATES.index(a["state"]), STATES.index(b["state"])
        if ib == ia + 1:
            continue
        if ib > ia and b.get("note", "").startswith("forced:"):
            continue
        return f"state_history jumps {a['state']} -> {b['state']} without a recorded forced note"
    if hist[-1]["state"] != entry["state"]:
        return "state does not match the last state_history entry"
    return None


def save(p, doc):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def cmd_init(a):
    p = Path(a.registry)
    if p.exists():
        fail("registry already exists; refusing to overwrite")
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"registry_version": 1, "entries": {}, "created": now()}
    save(p, doc)
    print(json.dumps({"status": "INITIALIZED", "path": str(p)}))


def cmd_add(a):
    p, doc = load(a.registry)
    if a.id in doc["entries"]:
        fail(f"entry exists: {a.id} (use transition/show; no silent overwrite)")
    if a.domain not in DOMAINS:
        fail(f"--domain must be one of {DOMAINS}")
    if not a.task:
        fail("at least one --task is required")
    if a.state not in READER_STATES:
        fail(f"discovery-side agents may only create entries in {sorted(READER_STATES)}; "
             "INSTALLED and beyond belong to the execution specialist")
    entry = {
        "id": a.id,
        "biological_domain": a.domain,
        "supported_tasks": a.task,
        "repository": a.repo,
        "state": a.state,
        "state_history": [{"state": st, "at": now(), "by": a.by,
                           **({"evidence": a.evidence} if st == a.state and a.evidence else {})}
                          for st in STATES[:STATES.index(a.state) + 1]],
        "last_verified": now(),
        "known_limitations": a.limit or ["unspecified"],
        **({"spec_path": a.spec_path} if a.spec_path else {}),
    }
    err = structural_check(entry)
    if err:
        fail(err)
    doc["entries"][a.id] = entry
    save(p, doc)
    print(json.dumps({"status": "ADDED", "id": a.id, "state": a.state}))


def cmd_show(a):
    p, doc = load(a.registry)
    if a.id:
        entry = doc["entries"].get(a.id)
        if entry is None:
            fail(f"no such entry: {a.id}")
        print(json.dumps(entry, indent=2, sort_keys=True))
        return
    for eid in sorted(doc["entries"]):
        e = doc["entries"][eid]
        print(f"{eid:36s} {e['state']:20s} {e['biological_domain']:14s} {e['repository'][:60]}")


def cmd_transition(a):
    p, doc = load(a.registry)
    entry = doc["entries"].get(a.id)
    if entry is None:
        fail(f"no such entry: {a.id}")
    if a.state not in STATES:
        fail(f"state must be one of {STATES}")
    cur, nxt = STATES.index(entry["state"]), STATES.index(a.state)
    if nxt <= cur:
        fail(f"backward/same transition refused: {entry['state']} -> {a.state}; "
             "re-verification is a new evidence note, not a state change")
    forced = nxt > cur + 1
    if forced and not a.force:
        fail(f"skipping states refused: {entry['state']} -> {a.state}; advance one state at a time "
             f"or pass --force with a recorded reason")
    step = {"state": a.state, "at": now(), "by": a.by}
    if a.evidence:
        step["evidence"] = a.evidence
    if a.note:
        step["note"] = (f"forced: {a.note}" if forced else a.note)
    elif forced:
        step["note"] = "forced: no reason supplied"
    entry["state"] = a.state
    entry["state_history"].append(step)
    entry["last_verified"] = now()
    err = structural_check(entry)
    if err:
        fail(f"post-transition entry invalid: {err}")
    save(p, doc)
    print(json.dumps({"status": "TRANSITIONED", "id": a.id, "from": STATES[cur], "to": a.state,
                      "forced": forced}))


def cmd_validate(a):
    p, doc = load(a.registry)
    problems = []
    for eid, entry in sorted(doc["entries"].items()):
        err = structural_check(entry)
        if err:
            problems.append(f"{eid}: {err}")
    print(json.dumps({"status": "PASS" if not problems else "FAIL",
                      "entries": len(doc["entries"]), "problems": problems}))
    raise SystemExit(0 if not problems else 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("registry"); i.set_defaults(fn=cmd_init)
    ad = sub.add_parser("add"); ad.add_argument("registry")
    ad.add_argument("--id", required=True); ad.add_argument("--domain", required=True)
    ad.add_argument("--task", action="append", required=True); ad.add_argument("--repo", required=True)
    ad.add_argument("--state", default="DISCOVERED", choices=sorted(READER_STATES))
    ad.add_argument("--limit", action="append")
    ad.add_argument("--evidence"); ad.add_argument("--spec-path"); ad.add_argument("--by", default="rna-model-discovery")
    ad.set_defaults(fn=cmd_add)
    s = sub.add_parser("show"); s.add_argument("registry"); s.add_argument("id", nargs="?"); s.set_defaults(fn=cmd_show)
    t = sub.add_parser("transition"); t.add_argument("registry"); t.add_argument("id"); t.add_argument("state")
    t.add_argument("--note"); t.add_argument("--evidence"); t.add_argument("--force", action="store_true")
    t.add_argument("--by", default="rna-agent-side")
    t.set_defaults(fn=cmd_transition)
    v = sub.add_parser("validate"); v.add_argument("registry"); v.set_defaults(fn=cmd_validate)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
