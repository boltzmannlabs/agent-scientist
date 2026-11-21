#!/usr/bin/env python3
"""Local package validation for rna-agent: routing fixtures, preflight cases, unit tests, checksums, strict SCI schema."""
import argparse
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]


def run(label, cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(("PASS " if r.returncode == 0 else "FAIL ") + label)
    if r.returncode != 0:
        print(r.stdout[-800:], r.stderr[-800:])
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sci-source", type=Path)
    ap.add_argument("--sci-python", type=Path)
    a = ap.parse_args()
    checks, failures = [], []

    if a.sci_source and a.sci_python:
        r = run("installed SCI strict schema", [str(a.sci_python), "-B", str(P / "scripts/sci_schema_probe.py"),
                                                "--source", str(a.sci_source), "--package", str(P)])
        (checks if r.returncode == 0 else failures).append("installed SCI strict schema")

    cases = json.loads((P / "tests/cases.json").read_text(encoding="utf-8-sig"))
    expected = json.loads((P / "tests/expected.json").read_text(encoding="utf-8-sig"))
    import route_request as rr
    sys.path.insert(0, str(P / "scripts"))
    import importlib
    rr = importlib.import_module("route_request")
    ok = 0
    total = 0
    for case, exp in zip(cases["routing_cases"], expected["routing_cases"]):
        total += 1
        out = rr.route(case["text"])
        if out.get("status") == exp["status"] and out.get("leaf") == exp.get("leaf"):
            ok += 1
        else:
            failures.append(f"routing {case['name']}: expected {exp} got {out.get('status')}/{out.get('leaf')}")
    for case, exp in zip(cases["preflight_cases"], expected["preflight_cases"]):
        total += 1
        out = rr.preflight(case["request"])
        if out.get("status") == exp["status"] and sorted(out.get("missing_inputs", [])) == sorted(exp["missing_inputs"]):
            ok += 1
        else:
            failures.append(f"preflight {case['name']}: expected {exp} got {out}")
    print(f"{'PASS' if ok == total else 'FAIL'} routing_fixtures {ok}/{total}")
    (checks if ok == total else failures).append("routing_fixtures")

    suite = unittest.defaultTestLoader.discover(str(P / "tests"), pattern="test_*.py")
    res = unittest.TextTestRunner(verbosity=0).run(suite)
    print(f"{'PASS' if res.wasSuccessful() else 'FAIL'} unit_tests {res.testsRun}")
    (checks if res.wasSuccessful() else failures).append(f"unit_tests({res.testsRun})")

    files = sorted(f for f in P.rglob("*") if f.is_file() and not f.is_symlink()
                   and f.name != "PROVENANCE.sha256" and "__pycache__" not in f.parts)
    (P / "tests/PROVENANCE.sha256").write_text(
        "".join(hashlib.sha256(f.read_bytes()).hexdigest() + "  " + str(f.relative_to(P)) + "\n" for f in files))
    print(f"PASS checksum_entries {len(files)}")
    checks.append(f"checksum_entries({len(files)})")

    manifest = json.loads((P / "manifest.yaml").read_text(encoding="utf-8-sig"))
    report = {"package_id": manifest["id"], "package_version": manifest["version"],
              "local": {"status": "failed" if failures else "passed",
                        "environment": f"Python {sys.version.split()[0]}; {__import__('platform').system()}; stdlib-only local QA (offline, no LLM)",
                        "checks": checks, "failures": failures},
              "integrated": {"status": "pending", "tested_commit": None,
                             "environment": "Not yet installed/enabled in an owning profile against a dev commit",
                             "checks": []},
              "scientific_execution": False, "live_agent_tested": False, "clean_install_tested": False}
    (P / "tests/validation.json").write_text(json.dumps(report, indent=2) + chr(10), encoding="utf-8")
    if failures:
        print("FAILURES: " + "; ".join(failures))
        return 1
    print(json.dumps({"package_version": manifest["version"], "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
