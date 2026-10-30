"""Retrosynthesis CLI task entrypoint tests; no live agent calls."""

import argparse
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from sci_cli import environment_tasks as tasks


def _args(**overrides):
    data = dict(target="CCO", inventory='["C", "O"]', constraints="{}", budget=None)
    return argparse.Namespace(**(data | overrides))


def _installed(tmp_path, monkeypatch):
    plugin = tmp_path / "plugins" / "retrosynthesis"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text("name: retrosynthesis\n")
    (plugin / "runtime.json").write_text(json.dumps({
        "SRG_PACKAGE_ROOT": str(tmp_path),
        "SRG_CHEMISTRY_PYTHON": sys.executable,
        "SRG_BACKEND_TIMEOUT_SECONDS": 120,
    }))
    monkeypatch.setattr(tasks, "_profile_home", lambda: tmp_path)
    monkeypatch.setattr(tasks, "_plugin_enabled", lambda home: True)
    return plugin


def test_run_validates_task_and_launches_normal_chat(tmp_path, monkeypatch):
    _installed(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(tasks, "_validate_task", lambda payload, runtime: seen.setdefault("task", payload))
    monkeypatch.setattr(tasks, "_launch_agent", lambda prompt, task, home: seen.update(prompt=prompt, launched_task=task, home=home))

    tasks.run_retrosynthesis_task(_args())

    assert seen["task"]["target"] == "CCO"
    assert seen["task"]["inventory"] == [{"smiles": "C"}, {"smiles": "O"}]
    assert seen["launched_task"] == seen["task"]
    assert "create" in seen["prompt"].lower()
    assert "submit" in seen["prompt"].lower()
    assert "CCO" in seen["prompt"]


def test_missing_plugin_fails_before_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tasks, "_profile_home", lambda: tmp_path)
    monkeypatch.setattr(tasks, "_plugin_enabled", lambda home: False)
    monkeypatch.setattr(tasks, "_launch_agent", lambda *_: pytest.fail("agent launched"))
    with pytest.raises(SystemExit) as exc:
        tasks.run_retrosynthesis_task(_args())
    assert exc.value.code == 2
    assert "sci environments install retrosynthesis" in capsys.readouterr().err


def test_plugin_enabled_respects_profile_config(monkeypatch):
    from sci_cli import config

    monkeypatch.setattr(config, "load_config_readonly", lambda: {
        "plugins": {"enabled": ["retrosynthesis"], "disabled": []},
    })
    assert tasks._plugin_enabled(Path("/tmp/example-root"))
    monkeypatch.setattr(config, "load_config_readonly", lambda: {
        "plugins": {"enabled": ["retrosynthesis"], "disabled": ["retrosynthesis"]},
    })
    assert not tasks._plugin_enabled(Path("/tmp/example-root"))


@pytest.mark.parametrize("overrides", [
    {"target": ""}, {"inventory": "not-json"}, {"inventory": "{}"},
    {"inventory": "[]"}, {"constraints": "[]"}, {"budget": "[]"},
])
def test_invalid_inputs_never_launch_agent(tmp_path, monkeypatch, overrides):
    _installed(tmp_path, monkeypatch)
    monkeypatch.setattr(tasks, "_launch_agent", lambda *_: pytest.fail("agent launched"))
    with pytest.raises(SystemExit) as exc:
        tasks.run_retrosynthesis_task(_args(**overrides))
    assert exc.value.code == 2


def test_json_input_accepts_file_and_rejects_oversize(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text('["C"]')
    assert tasks._read_json_input(str(path), "inventory") == ["C"]
    with pytest.raises(ValueError, match="too large"):
        tasks._read_json_input("[" + " " * tasks.MAX_INPUT_BYTES + "]", "inventory")


def _event(action, task_id="task-1", sid="session-1", *, ok=True, ids=None):
    arguments = {"task": {"task_id": task_id}} if action == "reset" else {"route_ids": ids or []}
    use = {"type": "tool_use", "name": "srg_action", "tool_call_id": action,
           "input": {"action": action, "arguments": arguments, **({"session_id": sid} if action != "reset" else {})}}
    output = ({"session_id": sid, "observation": {"status": "ok", "terminated": True,
               "result": {"submitted_route_ids": ids or [], "accepted_route_ids": ids or []}}} if action == "submit" else
              {"session_id": sid, "observation": {"status": "ok"}})
    if not ok:
        output["observation"]["status"] = "error"
    result = {"type": "tool_result", "name": "srg_action", "tool_call_id": action,
              "output": json.dumps(output), "is_error": False}
    return use, result


def test_tool_trace_requires_matching_successful_reset_and_submit():
    reset = _event("reset")
    submit = _event("submit", ids=["route-1"])
    expected = {"task_id": "task-1"}
    assert tasks._verify_trace([*reset, *submit], expected)
    assert not tasks._verify_trace([{"type": "result", "text": "I submitted a route"}], expected)
    assert not tasks._verify_trace([*reset], expected)
    assert not tasks._verify_trace([*reset, *_event("submit", sid="other")], expected)
    assert not tasks._verify_trace([*_event("reset", ok=False), *submit], expected)
    assert not tasks._verify_trace([*reset, *_event("submit", ok=False)], expected)
    assert not tasks._verify_trace([*reset, *_event("submit", ids=[])], expected)
    rejected = list(_event("submit", ids=["route-1"]))
    rejected_result = json.loads(rejected[1]["output"])
    rejected_result["observation"]["result"]["accepted_route_ids"] = []
    rejected[1] = {**rejected[1], "output": json.dumps(rejected_result)}
    assert not tasks._verify_trace([*reset, *rejected], expected)
    assert not tasks._verify_trace([*reset, *submit], {"task_id": "task-1", "target": "CCO"})
    altered_reset = ({**reset[0], "input": {"action": "reset", "arguments": {
        "task": {"task_id": "task-1", "target": "CCC"}}}}, reset[1])
    assert not tasks._verify_trace([*altered_reset, *submit], {"task_id": "task-1", "target": "CCO"})


def test_cli_parser_to_validated_task_without_live_agent(tmp_path, monkeypatch):
    from sci_cli.subcommands.environments import build_environments_parser

    _installed(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(tasks, "_validate_task", lambda task, runtime: seen.setdefault("task", task))
    monkeypatch.setattr(tasks, "_launch_agent", lambda *_: None)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_environments_parser(subparsers)
    args = parser.parse_args(["environments", "run", "retrosynthesis", "--target", "CCO",
                              "--inventory", '["C","O"]', "--constraints", "{}"])
    args.func(args)
    assert seen["task"]["target"] == "CCO"
    assert seen["task"]["inventory"] == [{"smiles": "C"}, {"smiles": "O"}]


def test_run_uses_default_root_when_active_profile_is_named(monkeypatch, tmp_path):
    import sci_constants

    root = tmp_path / "main"
    named = root / "profiles" / "sirna"
    monkeypatch.setattr(sci_constants, "get_sci_home", lambda: named)
    monkeypatch.setattr(sci_constants, "get_default_sci_root", lambda *, home: root)
    assert tasks._profile_home() == root


def _fake_chat(monkeypatch, events, *, exit_code=0):
    from sci_cli import environments_install

    # The stream and child process are mocked; do not require a published Sci
    # executable on the CI runner's PATH for these task-flow unit tests.
    monkeypatch.setattr(environments_install, "_sci_executable", lambda: sys.executable)
    calls = {}

    class Process:
        stdout = io.StringIO("".join(json.dumps(event) + "\n" for event in events))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def wait(self):
            return exit_code

    def popen(command, **kwargs):
        calls["command"] = command
        calls["env"] = kwargs["env"]
        calls["prompt"] = Path(command[command.index("--query-file") + 1]).read_text()
        return Process()

    monkeypatch.setattr(tasks.subprocess, "Popen", popen)
    return calls


def test_launch_checks_real_tool_events_and_keeps_main_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "named-profile-secret")
    events = [*_event("reset"), *_event("submit", ids=["route-1"]),
              {"type": "result", "session_id": "agent-session", "exit_code": 0, "text": "Route reviewed"}]
    calls = _fake_chat(monkeypatch, events)
    tasks._launch_agent("task prompt", {"task_id": "task-1"}, tmp_path)
    assert calls["prompt"] == "task prompt"
    assert calls["env"]["SCI_HOME"] == str(tmp_path)
    assert "OPENAI_API_KEY" not in calls["env"]
    assert calls["command"][1:3] == ["-p", "default"]
    assert Path(calls["command"][0]).is_absolute()
    assert "-m" not in calls["command"]
    assert "--format" in calls["command"] and "stream-json" in calls["command"]
    assert "--model" not in calls["command"] and "--provider" not in calls["command"]
    assert "Route reviewed" in capsys.readouterr().out


def test_launch_rejects_prose_without_submission(tmp_path, monkeypatch, capsys):
    _fake_chat(monkeypatch, [{"type": "result", "session_id": "agent-session",
                            "exit_code": 0, "text": "I submitted a route"}])
    monkeypatch.setattr(tasks, "_stored_events", lambda *_: [])
    with pytest.raises(SystemExit) as exc:
        tasks._launch_agent("task prompt", {"task_id": "task-1"}, tmp_path)
    assert exc.value.code == 1
    assert "without a verified route submission" in capsys.readouterr().err


def test_launch_uses_full_stored_receipt_when_stream_is_clipped(tmp_path, monkeypatch):
    reset = _event("reset")
    submit = list(_event("submit", ids=["route-1"]))
    submit[1] = {**submit[1], "output": submit[1]["output"][:30] + "..."}
    _fake_chat(monkeypatch, [*reset, *submit,
                            {"type": "result", "session_id": "agent-session", "exit_code": 0}])
    monkeypatch.setattr(tasks, "_stored_events", lambda *_: [*_event("reset"), *_event("submit", ids=["route-1"])])
    tasks._launch_agent("task prompt", {"task_id": "task-1"}, tmp_path)


@pytest.mark.parametrize("dispatch", ["direct", "lazy", "ambiguous"])
def test_stored_events_reconstructs_tool_calls(tmp_path, monkeypatch, dispatch):
    import sci_state

    def function(arguments):
        if dispatch == "direct":
            return {"name": "srg_action", "arguments": json.dumps(arguments)}
        calls = [{"name": "srg_action", "arguments": arguments}]
        if dispatch == "ambiguous":
            calls = calls * 2
        return {"name": "tool_call", "arguments": json.dumps({"calls": calls})}

    class DB:
        def __init__(self, **kwargs):
            assert kwargs["db_path"] == tmp_path / "state.db"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get_messages_as_conversation(self, session_id, **kwargs):
            assert session_id == "agent-session"
            reset = _event("reset")
            submit = _event("submit", ids=["route-1"])
            return [
                {"role": "assistant", "tool_calls": [{"id": "a", "function": function(reset[0]["input"])}]},
                {"role": "tool", "tool_call_id": "a", "content": reset[1]["output"]},
                {"role": "assistant", "tool_calls": [{"id": "b", "function": function(submit[0]["input"])}]},
                {"role": "tool", "tool_call_id": "b", "content":
                 "<persisted-output>\nFull output saved to: /tmp/untrusted-other-path\n</persisted-output>"},
            ]

    spill = tmp_path / "cache" / "spillover"
    spill.mkdir(parents=True)
    full_submit = _event("submit", ids=["route-1"])[1]["output"] + " " * 6000
    (spill / "b.txt").write_text(full_submit)
    monkeypatch.setattr(sci_state, "SessionDB", DB)
    verified = tasks._verify_trace(tasks._stored_events(tmp_path, "agent-session"), {"task_id": "task-1"})
    assert verified is (dispatch != "ambiguous")


def test_spill_receipt_ignores_embedded_path_and_rejects_oversize(tmp_path, monkeypatch):
    spill = tmp_path / "cache" / "spillover"
    spill.mkdir(parents=True)
    content = "<persisted-output>Full output saved to: /tmp/evil</persisted-output>"
    (spill / "call-1.txt").write_text('{"status":"ok"}')
    assert tasks._full_tool_receipt(tmp_path, "call-1", content) == '{"status":"ok"}'
    monkeypatch.setattr(tasks, "MAX_RECEIPT_BYTES", 64)
    (spill / "call-1.txt").write_text("x" * 65)
    assert tasks._full_tool_receipt(tmp_path, "call-1", content) == ""


def test_launch_from_unrelated_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = _fake_chat(monkeypatch, [*_event("reset"), *_event("submit", ids=["route-1"]),
                                  {"type": "result", "session_id": "agent-session", "exit_code": 0}])
    tasks._launch_agent("task prompt", {"task_id": "task-1"}, tmp_path)
    assert Path(calls["command"][0]).is_absolute()


def test_launch_environment_uses_default_home_with_named_profile_override(tmp_path, monkeypatch):
    from sci_constants import reset_sci_home_override, set_sci_home_override

    main_home = tmp_path / "main"
    named_home = main_home / "profiles" / "sirna"
    token = set_sci_home_override(str(named_home))
    try:
        calls = _fake_chat(monkeypatch, [*_event("reset"), *_event("submit", ids=["route-1"]),
                                      {"type": "result", "session_id": "agent-session", "exit_code": 0}])
        tasks._launch_agent("task prompt", {"task_id": "task-1"}, main_home)
    finally:
        reset_sci_home_override(token)
    assert calls["env"]["SCI_HOME"] == str(main_home)


def test_validation_uses_chemistry_python_and_returns_canonical_task(tmp_path):
    root = Path(__file__).resolve().parents[3] / "srg-releases" / "retrosynthesis-managed-published" / "environments" / "retrosynthesis"
    python = Path(os.environ.get("SRG_TEST_CHEMISTRY_PYTHON", root.parents[2] / "retrosynthesis-managed-validate" / "venv" / "bin" / "python"))
    if not root.is_dir() or not python.is_file():
        pytest.skip("published chemistry source/runtime unavailable")
    task = tasks._build_task(_args())
    canonical = tasks._validate_task(task, {"SRG_PACKAGE_ROOT": str(root), "SRG_CHEMISTRY_PYTHON": str(python)})
    assert canonical["target"] == "CCO"
    assert canonical["inventory"][0]["smiles"] == "C"
    assert canonical["budget"]["top_k"] == 10
    with pytest.raises(ValueError, match="target"):
        tasks._validate_task({**task, "target": "not-a-smiles"}, {
            "SRG_PACKAGE_ROOT": str(root), "SRG_CHEMISTRY_PYTHON": str(python),
        })


def test_chemistry_validation_reports_child_errors_and_accepts_json(tmp_path, monkeypatch):
    source = tmp_path / "src" / "synthesis_route_gym"
    source.mkdir(parents=True)
    (source / "schemas.py").touch()
    runtime = {"SRG_PACKAGE_ROOT": str(tmp_path), "SRG_CHEMISTRY_PYTHON": sys.executable}
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"target":"CCO"}', stderr="")

    monkeypatch.setattr(tasks.subprocess, "run", run)
    assert tasks._validate_task({"target": "CCO"}, runtime) == {"target": "CCO"}
    assert calls[0][0][0] == sys.executable
    assert calls[0][1]["encoding"] == "utf-8"
    assert json.loads(calls[0][1]["input"])["target"] == "CCO"

    monkeypatch.setattr(tasks.subprocess, "run", lambda *_args, **_kwargs:
                        SimpleNamespace(returncode=2, stdout="", stderr="bad input\n"))
    with pytest.raises(ValueError, match="bad input"):
        tasks._validate_task({"target": "bad"}, runtime)
