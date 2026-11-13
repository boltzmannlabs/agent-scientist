"""#53: recovery advice preserves errors, partial results and execution boundaries."""
import json
import time
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("error", [
    "KeyError: 'specialist_ledger'",
    "sqlite3.OperationalError: no such column: created_at",
    "AssertionError\r\n",
    "ValueError: New fields require existing final field anchor in changes.",
    "ZeroDivisionError: division by zero",
    "AttributeError: 'dict' object has no attribute 'specialist_calls'",
    "FileNotFoundError: missing-tracking.json",
    "TypeError: object of type 'NoneType' has no len()",
    "RuntimeError: an unrecognized failure",
    "Process exited without a traceback",
    "",
])
def test_schema_failure_guidance_preserves_error_contract_across_result_paths(error, monkeypatch):
    from tools import code_execution_tool as execution
    from tools.terminal_hints import annotate_failure
    from tools.terminal_tool_result import _failure_hint

    hint = execution._sandbox_failure_hint(error)
    assert hint and "authorized" in hint and "artifacts" in hint
    # Diagnostics do not interpolate arbitrary exception data back into advice.
    assert "specialist_ledger" not in hint and "created_at" not in hint
    output = "x" * 8000 + "\n" + error
    assert annotate_failure("python tracking.py", 1, output) == hint
    assert _failure_hint("python tracking.py", 1, output, exit_note=None) == hint
    assert annotate_failure("python tracking.py", 0, error) is None
    assert _failure_hint("python tracking.py", 137, error, exit_note="Process killed") is None
    remote = json.loads(execution._finish_remote_kernel_result(
        {"status": "error", "error": error, "stdout": "Output saved before failure.", "traceback": error},
        timeout=30, exec_start=time.monotonic()))
    assert remote["status"] == "error" and remote.get("error", "") == error
    assert "Output saved before failure." in remote["output"] and remote["hint"] == hint
    for status in ("success", "timeout", "interrupted"):
        result = json.loads(execution._finish_remote_kernel_result(
            {"status": status, "error": error}, timeout=30, exec_start=time.monotonic()))
        assert "hint" not in result
    assert annotate_failure("python tracking.py", 130, output) is None
    assert annotate_failure("python tracking.py", -15, output) is None
    assert "authorization" in execution._sandbox_failure_hint("Permission denied")

    # A controlled backend exercises the remote standalone result path without
    # installing software, opening SSH connections or executing a scientific job.
    env = Mock()
    env.get_temp_dir.return_value = "/fixture"
    env.execute.side_effect = lambda command, **kw: {
        "output": output if "python3 script.py" in command else "",
        "returncode": 1 if "python3 script.py" in command else 0,
    }
    monkeypatch.setattr(execution, "_ship_file_to_remote", Mock())
    monkeypatch.setattr(execution, "_rpc_poll_loop", Mock())
    result = json.loads(execution._run_remote_per_call(
        env, "ssh", "raise KeyError('fixture')", "owner", frozenset(),
        timeout=30, max_tool_calls=5, exec_start=time.monotonic()))
    assert result["status"] == "error" and result["exit_code"] == 1
    assert result["hint"] == hint and error in result["output"]
