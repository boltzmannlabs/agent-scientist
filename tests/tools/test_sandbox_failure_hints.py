"""Tests for execute_code sandbox failure hints."""

import json


from tools.code_execution_tool import _sandbox_failure_hint, execute_code


class TestSandboxFailureHint:
    def test_unavailable_tool_import_lists_available(self):
        err = ("Traceback (most recent call last):\n  File \"script.py\", line 1\n"
               "ImportError: cannot import name 'browser_navigate' from 'sci_tools'")
        h = _sandbox_failure_hint(err, enabled_tools={"terminal", "read_file"})
        assert "browser_navigate" in h
        assert "read_file" in h and "terminal" in h




    def test_unknown_failure_requires_diagnosis_and_preserves_partial_work(self):
        hint = _sandbox_failure_hint("ZeroDivisionError: division by zero")
        assert "Inspect" in hint and "do not replay" in hint and "authorized task" in hint

    def test_empty_diagnostics_do_not_invent_a_cause(self):
        assert "do not invent an error cause" in _sandbox_failure_hint("")


class TestLiveSandboxHint:
    def test_bad_import_produces_hint_field(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
        r = json.loads(execute_code(
            "from sci_tools import totally_fake_tool\nprint('unreachable')",
            task_id="t-sbhint",
        ))
        assert r["status"] == "error"
        assert "hint" in r
        assert "totally_fake_tool" in r["hint"]


    def test_successful_script_has_no_hint(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
        r = json.loads(execute_code("print('fine')", task_id="t-sbhint"))
        assert r["status"] == "success"
        assert "hint" not in r
