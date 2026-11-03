"""Run identity/review software checks; report skipped RDKit checks explicitly."""
import io
import json
from pathlib import Path
import unittest

from audit import Chem, rdBase


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent),
                                              pattern="test_audit.py")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    print(json.dumps({"scope": "Local identity/review-binding software checks, no predictions",
                      "tests_run": result.testsRun, "successful": result.wasSuccessful(),
                      "failures": len(result.failures), "errors": len(result.errors),
                      "skipped": len(result.skipped), "rdkit_available": Chem is not None,
                      "rdkit_version": rdBase.rdkitVersion if rdBase else None,
                      "test_log": output.getvalue()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
