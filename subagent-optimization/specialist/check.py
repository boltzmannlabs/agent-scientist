"""Report artificial handoff tests. No native host or model is invoked."""
import io
import json
import unittest


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromName("specialist.test_advisor")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    print(json.dumps({"scope": "Artificial specialist packet/answer checks, no model or native execution",
                      "tests_run": result.testsRun, "successful": result.wasSuccessful(),
                      "failures": len(result.failures), "errors": len(result.errors),
                      "skipped": len(result.skipped), "test_log": output.getvalue()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
