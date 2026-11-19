#!/usr/bin/env python3
"""Read-scope guard v2 for leaf specialists (stdlib only; invoke as: python3 read_guard.py ...).

v2 closes the v1 flaw where the guarded model seeded its own allowed roots: authorization is now derived ONLY
from the verbatim parent assignment text. init takes the saved assignment file; authorized roots are extracted
exclusively from lines carrying an explicit authorization marker; the assignment is hashed and verify detects
tampering. There is no --allow flag.

Commands:
  init   --assignment <file> --log <log.json> [--auto <dir>]...   # roots = auto + extracted-from-text only
  check  --log <log.json> <path>...                               # verdict per path (logged)
  show   --log <log.json>                                         # dump verdicts for the report
  verify --log <log.json> [--assignment <file>]                   # 0 iff consistent, no overridden DENY,
                                                                  # and (when given) assignment hash unchanged

Authorization markers (case-insensitive) whose line authorizes the absolute paths on it:
  PARENT READ AUTHORIZATION · authorized to read · you are authorized · read authorization

Exit codes: 0 ok/allow, 2 deny or verify failure, 1 usage/io error.
"""
import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path

MARKERS = re.compile(r"(parent read authorization|authorized to read|you are authorized|read authorization)", re.I)
ABS_PATH = re.compile(r"(?<![\w.])/(?:[\w.-]+/)*[\w.-]+")


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(p):
    return json.loads(Path(p).expanduser().read_text(encoding="utf-8-sig"))


def save(p, doc):
    q = Path(p).expanduser()
    q.parent.mkdir(parents=True, exist_ok=True)
    tmp = q.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(q)


def authorized_roots_from_text(text):
    roots = []
    for line in text.splitlines():
        if MARKERS.search(line):
            for m in ABS_PATH.finditer(line):
                p = m.group(0)
                while p.endswith("."):
                    p = p.rstrip(".")
                if len(p) > 1 and p not in roots:
                    roots.append(p)
    return roots


def is_within(path: Path, root: str) -> bool:
    try:
        path.resolve().relative_to(Path(root).expanduser().resolve())
        return True
    except ValueError:
        return False


def matching_root(roots, path_str):
    p = Path(path_str).expanduser()
    for r in roots:
        if is_within(p, r):
            return r
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("--assignment", required=True); i.add_argument("--log", required=True)
    i.add_argument("--auto", action="append", default=[], help="auto-allowed root: package/workspace/output dir")
    c = sub.add_parser("check"); c.add_argument("--log", required=True); c.add_argument("paths", nargs="+")
    s = sub.add_parser("show"); s.add_argument("--log", required=True)
    v = sub.add_parser("verify"); v.add_argument("--log", required=True); v.add_argument("--assignment")
    a = ap.parse_args()

    if a.cmd == "init":
        atext = Path(a.assignment).expanduser().read_text(encoding="utf-8-sig")
        extracted = authorized_roots_from_text(atext)
        roots = sorted(set(str(Path(x).expanduser().resolve()) for x in (list(a.auto) + extracted)))
        save(a.log, {"created": now(), "allowed_roots": roots,
                     "extracted_from_assignment": sorted(str(Path(x).resolve()) for x in extracted),
                     "assignment_sha256": hashlib.sha256(atext.encode()).hexdigest(),
                     "note": "roots derive only from the verbatim assignment text; there is no manual grant"})
        print(json.dumps({"status": "INITIALIZED", "allowed_roots": roots,
                          "authorized_by_assignment": len(extracted) > 0}))
        return 0

    if a.cmd == "check":
        log = load(a.log)
        any_deny = False
        for path in a.paths:
            root = matching_root(log["allowed_roots"], path)
            verdict = "ALLOW" if root else "DENY"
            any_deny = any_deny or not root
            log["verdicts"] = log.get("verdicts", [])
            log["verdicts"].append({"at": now(), "path": str(Path(path).expanduser().resolve()),
                                    "verdict": verdict, "matching_root": root})
        save(a.log, log)
        print(json.dumps({"status": "COMPLETE" if not any_deny else "DENIED",
                          "verdicts": log["verdicts"][-len(a.paths):]}, indent=1))
        return 2 if any_deny else 0

    if a.cmd == "show":
        log = load(a.log)
        print(json.dumps(log, indent=1, sort_keys=True))
        denies = [v["path"] for v in log.get("verdicts", []) if v["verdict"] == "DENY"]
        return 2 if denies else 0

    if a.cmd == "verify":
        log = load(a.log)
        problems = []
        for v in log.get("verdicts", []):
            root = matching_root(log["allowed_roots"], v["path"])
            expect = "ALLOW" if root else "DENY"
            if v["verdict"] != expect:
                problems.append(f"{v['path']}: logged {v['verdict']} but roots say {expect}")
        if getattr(a, "assignment", None):
            atext = Path(a.assignment).expanduser().read_text(encoding="utf-8-sig")
            h = hashlib.sha256(atext.encode()).hexdigest()
            if h != log.get("assignment_sha256"):
                problems.append("assignment file changed since init (tamper suspect); re-derive authorization")
        denies = [v["path"] for v in log.get("verdicts", []) if v["verdict"] == "DENY"]
        ok = not problems
        print(json.dumps({"status": "PASS" if ok else "FAIL", "checks": len(log.get("verdicts", [])),
                          "denied": denies, "problems": problems}))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
