"""Run artificial context checks and print evidence without writing files."""
import io
import json
from pathlib import Path
import unittest


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent),
                                              pattern="test_context_contract.py")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
    print(json.dumps({"scope": "Artificial context/advisory-contract checks only",
                      "tests_run": result.testsRun, "successful": result.wasSuccessful(),
                      "failures": len(result.failures), "errors": len(result.errors),
                      "skipped": len(result.skipped), "test_log": output.getvalue()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
