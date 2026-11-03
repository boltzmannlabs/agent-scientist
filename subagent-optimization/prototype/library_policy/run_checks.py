"""Reproduce software checks; write only small local result artifacts."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent


def main():
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_policy.py")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    demo = subprocess.run([sys.executable, "-B", str(HERE / "demo.py")], cwd=HERE,
                          text=True, capture_output=True, check=True)
    context_dir = HERE.parent / "context_contract"
    context_process = subprocess.run([sys.executable, "-B", str(context_dir / "check.py")],
                                     cwd=context_dir, text=True, capture_output=True, check=True)
    context = json.loads(context_process.stdout)
    context_log = context.pop("test_log")
    audit_dir = HERE.parent / "library_audit"
    audit_process = subprocess.run([sys.executable, "-B", str(audit_dir / "check.py")],
                                   cwd=audit_dir, text=True, capture_output=True, check=True)
    audit = json.loads(audit_process.stdout)
    audit_log = audit.pop("test_log")
    specialist_dir = HERE.parents[1] / "specialist"
    specialist_process = subprocess.run([sys.executable, "-B", "-m", "specialist.check"],
                                        cwd=HERE.parents[1], text=True, capture_output=True, check=True)
    specialist = json.loads(specialist_process.stdout)
    specialist_log = specialist.pop("test_log")
    names = ("policy.py", "fixtures.py", "test_policy.py", "demo.py", "run_checks.py")
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Artificial policy/context mechanics and local structural-identity software checks",
        "python": sys.version.split()[0], "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "successful": result.wasSuccessful(),
        "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in names},
        "demonstration": json.loads(demo.stdout),
        "context_checks": context,
        "context_source_sha256": {name: hashlib.sha256((context_dir / name).read_bytes()).hexdigest()
                                  for name in ("context_contract.py", "fixtures.py", "test_context_contract.py", "check.py", "demo.py")},
        "library_audit_checks": audit,
        "library_audit_source_sha256": {name: hashlib.sha256((audit_dir / name).read_bytes()).hexdigest()
                                        for name in ("audit.py", "test_audit.py", "check.py", "inspect_assets.py")},
        "specialist_advisor_checks": specialist,
        "specialist_source_sha256": {name: hashlib.sha256((specialist_dir / name).read_bytes()).hexdigest()
                                      for name in ("advisor.py", "definition.json", "fixtures.py", "test_advisor.py",
                                                   "demo.py", "check.py", "test_native.py")},
        "native_specialist_development_definition": True,
        "native_profile_installed_by_this_work": False,
        "native_canary": "separate host-runner record; not part of this suite",
        "scientific_benefit": "not_evaluated",
        "scientific_jobs_submitted": 0,
    }
    destination = HERE.parents[1] / "results"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "software-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    (destination / "policy-tests.log").write_text(output.getvalue())
    (destination / "context-tests.log").write_text(context_log)
    (destination / "library-audit-tests.log").write_text(audit_log)
    (destination / "specialist-advisor-tests.log").write_text(specialist_log)
    print(json.dumps({"policy_tests": result.testsRun, "context_tests": context["tests_run"],
                      "library_audit_tests": audit["tests_run"], "library_audit_skipped": audit["skipped"],
                      "specialist_advisor_tests": specialist["tests_run"],
                      "successful": result.wasSuccessful() and context["successful"] and audit["successful"] and specialist["successful"],
                      "report": str(destination / "software-validation.json")}, indent=2))
    return 0 if result.wasSuccessful() and context["successful"] and audit["successful"] and specialist["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
