#!/usr/bin/env python3
"""Specialist roster: the orchestrator's self-knowledge of its sub-agents.

Commands:
  roster.py list                 # one line per specialist: name, domains, modes
  roster.py describe <name>      # full capability card (JSON)
  roster.py capabilities <text>  # rank specialists by capability-keyword overlap with the text
  roster.py check                # roster keys == routing-table leaf keys (consistency)

Exit 0 ok; 2 unknown specialist / consistency failure.
"""
import argparse
import json
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1]
ROSTER = json.loads((P / "references/subagent-roster.json").read_text(encoding="utf-8-sig"))
TABLE = json.loads((P / "references/routing-table.json").read_text(encoding="utf-8-sig"))


def specialists():
    return ROSTER["specialists"]


def score(text, spec):
    t = (text or "").lower()
    hits = []
    for cap in spec.get("capabilities", []) + [f"{m} {d}" for m in spec.get("modes", []) for d in spec.get("domains", [])]:
        words = [w for w in re.findall(r"[a-z]{4,}", cap.lower())]
        if any(w in t for w in words):
            hits.append(cap[:70])
    for d in spec.get("domains", []):
        if d.lower() in t:
            hits.append(f"domain:{d}")
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    d = sub.add_parser("describe"); d.add_argument("name")
    c = sub.add_parser("capabilities"); c.add_argument("text")
    sub.add_parser("check")
    a = ap.parse_args()

    if a.cmd == "list":
        for s in specialists():
            print(f"{s['name']:36s} domains={','.join(s['domains']):28s} modes={','.join(s['modes'])}")
        return 0
    if a.cmd == "describe":
        s = next((x for x in specialists() if x["name"] == a.name), None)
        if not s:
            print(json.dumps({"status": "INVALID", "error": f"unknown specialist: {a.name}"}))
            return 2
        print(json.dumps(s, indent=1, sort_keys=True))
        return 0
    if a.cmd == "capabilities":
        ranked = sorted(((len(score(a.text, s)), s["name"]) for s in specialists()), reverse=True)
        out = [{"specialist": n, "matched_signals": h,
                "required_inputs": next(x["required_inputs"] for x in specialists() if x["name"] == n)}
               for h, n in ranked if h > 0]
        print(json.dumps({"query": a.text[:80], "ranked": out}, indent=1))
        return 0
    if a.cmd == "check":
        roster_keys = sorted(s["name"] for s in specialists())
        table_keys = sorted(r["leaf"] for r in TABLE["routes"])
        ok = roster_keys == table_keys
        print(json.dumps({"status": "PASS" if ok else "FAIL",
                          "roster": roster_keys, "routing_table": table_keys,
                          "problems": [] if ok else [f"keys differ: {set(roster_keys) ^ set(table_keys)}"]}))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
