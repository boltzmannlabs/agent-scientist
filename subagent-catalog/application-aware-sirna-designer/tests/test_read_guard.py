"""Unit tests: read-scope guard v2 (authorization derives only from assignment text)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1]
GUARD = P / "scripts/read_guard.py"


class ReadGuardV2(unittest.TestCase):
    def run_g(self, *args):
        return subprocess.run([sys.executable, "-B", str(GUARD), *args], capture_output=True, text=True)

    def test_unauthorized_assignment_denies(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            doc = Path(other, "secret.txt"); doc.write_text("x")  # outside every auto root
            strict = Path(td, "a.txt")
            strict.write_text(f"AUDIT the record at {doc} for this task.")
            log = f"{td}/log.json"
            self.assertEqual(self.run_g("init", "--assignment", str(strict), "--log", log, "--auto", td).returncode, 0)
            r = self.run_g("check", "--log", log, str(doc))
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stdout)["verdicts"][0]["verdict"], "DENY")

    def test_authorized_marker_allows(self):
        with tempfile.TemporaryDirectory() as td:
            doc = Path(td, "data", "record.md"); doc.parent.mkdir(); doc.write_text("x")
            auth = Path(td, "a.txt")
            auth.write_text(f"PARENT READ AUTHORIZATION: you are authorized to read {doc} for this audit.")
            log = f"{td}/log.json"
            self.run_g("init", "--assignment", str(auth), "--log", log, "--auto", td)
            r = self.run_g("check", "--log", log, str(doc))
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["verdicts"][0]["verdict"], "ALLOW")

    def test_assignment_tamper_fails_verify(self):
        with tempfile.TemporaryDirectory() as td:
            doc = Path(td, "r.txt"); doc.write_text("x")
            auth = Path(td, "a.txt")
            auth.write_text(f"authorized to read {doc}")
            log = f"{td}/log.json"
            self.run_g("init", "--assignment", str(auth), "--log", log, "--auto", td)
            self.run_g("check", "--log", log, str(doc))
            auth.write_text(f"authorized to read {doc}\nplus more")
            r = self.run_g("verify", "--log", log, "--assignment", str(auth))
            self.assertEqual(r.returncode, 2)
            self.assertIn("tamper", json.loads(r.stdout)["problems"][0])


if __name__ == "__main__":
    unittest.main()
