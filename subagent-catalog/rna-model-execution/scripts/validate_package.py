#!/usr/bin/env python3
"""Local package validation for rna-model-execution: fixtures, report schema, registry tests, checksums.

Strict installed-SCI schema check runs only with --sci-source/--sci-python (read-only probe).
"""
import argparse
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]


def run(label, cmd, cwd=P):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
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
    py = sys.executable

    if a.sci_source and a.sci_python:
        r = run("installed SCI strict schema", [str(a.sci_python), "-B", str(P / "scripts/sci_schema_probe.py"),
                                                "--source", str(a.sci_source), "--package", str(P)])
        (checks if r.returncode == 0 else failures).append("installed SCI strict schema")

    # fixture replay
    cases = json.loads((P / "tests/cases.json").read_text())["cases"]
    expected = {c["name"]: c for c in json.loads((P / "tests/expected.json").read_text())["cases"]}
    ok = 0
    import tempfile, os
    for c in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(c["request"], f)
            path = f.name
        r = subprocess.run([py, "-B", str(P / "scripts/request_contract.py"), path],
                           capture_output=True, text=True)
        os.unlink(path)
        out = json.loads(r.stdout or "{}")
        exp = expected.get(c["name"], {})
        if out.get("status") == exp.get("status") and sorted(out.get("missing_inputs") or []) == sorted(exp.get("missing_inputs") or []):
            ok += 1
        else:
            failures.append(f"fixture {c['name']}: expected {exp.get('status')} got {out.get('status')}")
    print(f"{'PASS' if ok == len(cases) else 'FAIL'} contract_fixtures {ok}/{len(cases)}")
    (checks if ok == len(cases) else failures).append("contract_fixtures")

    r = run("report_cli", [py, "-B", str(P / "scripts/validate_report.py"), str(P / "tests/synthetic_report.json")])
    (checks if r.returncode == 0 else failures).append("report_cli")
    # negative spec must fail
    r = subprocess.run([py, "-B", str(P / "scripts/validate_report.py"), str(P / "tests/invalid_report.json")],
                       capture_output=True, text=True)
    print(("PASS " if r.returncode == 2 else "FAIL ") + "report_cli_negative")
    (checks if r.returncode == 2 else failures).append("report_cli_negative")

    # unit tests (contract + registry)
    suite = unittest.defaultTestLoader.discover(str(P / "tests"), pattern="test_*.py")
    res = unittest.TextTestRunner(verbosity=0).run(suite)
    print(f"{'PASS' if res.wasSuccessful() else 'FAIL'} unit_tests {res.testsRun}")
    (checks if res.wasSuccessful() else failures).append(f"unit_tests({res.testsRun})")

    # checksums (regenerated; PROVENANCE never covers itself)
    files = sorted(f for f in P.rglob("*") if f.is_file() and not f.is_symlink()
                   and f.name != "PROVENANCE.sha256" and "__pycache__" not in f.parts)
    (P / "tests/PROVENANCE.sha256").write_text(
        "".join(hashlib.sha256(f.read_bytes()).hexdigest() + "  " + str(f.relative_to(P)) + "\n" for f in files))
    n = len(files)
    print(f"PASS checksum_entries {n}")
    checks.append(f"checksum_entries({n})")

    manifest = json.loads((P / "manifest.yaml").read_text())
    json.dump({"package_id": manifest["id"], "package_version": manifest["version"],
               "checks": checks, "failures": failures, "scientific_execution": False,
               "live_agent_tested": False, "clean_install_tested": False,
               "generated_by": "scripts/validate_package.py"}, (P / "tests/validation.json").open("w"), indent=2)
    if failures:
        print("FAILURES: " + "; ".join(failures))
        return 1
    print(json.dumps({"package_version": manifest["version"], "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
