"""Real fresh-profile workers against a loopback-only, controlled model provider."""

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home


@pytest.mark.parametrize("mode", ["legacy-worker", "native", "native-reference", "legacy-cli"])
def test_fresh_profile_worker_turns_restart_and_a_b_a_isolation(tmp_path, monkeypatch, mode):
    from sci_cli.science_profiles import ProfileSpec, create
    from sci_cli.science_profile_commands import activate
    from types import SimpleNamespace
    from unittest.mock import Mock
    native = mode in {"native", "native-reference"}

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / ".sci"
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *a: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *a: None)
    with FakeLLMServer(default_text="SCI fixture response", aux=lambda _: Text("SCI fixture response")) as server:
        write_sci_home(home, server.base_url)
        if native:
            from sci_cli.config import read_user_config_raw, atomic_config_replace
            cfg = read_user_config_raw(home / "config.yaml")
            cfg["model"]["provider"] = "fixture-provider"
            cfg["providers"] = {"fixture-provider": {"api": server.base_url}}
            if mode == "native-reference":
                cfg["model"]["api_key"] = "${SCI_FIXTURE_LLM_KEY}"
                cfg["providers"]["fixture-provider"]["key_env"] = "SCI_FIXTURE_LLM_KEY"
                with (home / ".env").open("a") as env_file:
                    env_file.write("\nSCI_FIXTURE_LLM_KEY=sk-shared-profile-test\n")
            atomic_config_replace(home / "config.yaml", cfg)
            if mode == "native":
                (home / "auth.json").write_text(json.dumps({"version": 1, "credential_pool": {
                    "fixture-provider": [{"id": "fixture", "label": "shared fixture", "auth_type": "api_key",
                        "priority": 0, "source": "manual", "access_token": "sk-shared-profile-test"}]}}))
        skill = home / "skills/science/fixture"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: fixture\ndescription: Review scientific evidence\n---\nSeparate evidence from hypotheses.\n")
        from sci_cli.native_profile_creation import create_native
        from sci_cli.profiles import get_profile_dir
        profiles = []
        for name, purpose in (("antibody", "ANTIBODY_ONLY"), ("molecule", "MOLECULE_ONLY")):
            if native:
                profiles.append(create_native(name, home, ["science/fixture"], [], [],
                    {"backend": "local", "cwd": str(get_profile_dir(name) / "workspace")}, "Cite evidence. " + purpose))
            else:
                profiles.append(create(ProfileSpec(name, purpose, "Cite evidence", "", setup_pending=True,
                                                   skills=["science/fixture"]), home))
        if not native:
            from sci_cli.config import atomic_config_replace, read_user_config_raw
            from sci_cli.native_profile_update import update_wizard
            from sci_cli.science_profiles import MANIFEST
            for target in profiles:
                # Exercise an actual pre-upgrade approval through the public wizard,
                # then boot a separate worker/CLI with the migrated files.
                record = json.loads((target / MANIFEST).read_text())
                record.pop("config_review")
                (target / MANIFEST).write_text(json.dumps(record))
                cfg = read_user_config_raw(target / "config.yaml")
                cfg["display"] = {"skin": "mono"}
                atomic_config_replace(target / "config.yaml", cfg)
                ui = SimpleNamespace(show=Mock(), choose=Mock(return_value="Approve profile repair"))
                update_wizard(SimpleNamespace(), f'/Update_profile "{target.name}"', ui)
                assert "Saved profile" in ui.show.call_args.args[0]
        parent = SimpleNamespace(agent=SimpleNamespace(system_prompt="cached", tools=["unchanged"],
                                                      _flush_messages_to_session_db=Mock()),
                                 conversation_history=[{"role": "user", "content": "main only"}],
                                 _app=SimpleNamespace(is_running=True, loop=Mock(), exit=Mock()))
        before = (home / "config.yaml").read_bytes()
        for target in (profiles[0], profiles[1], profiles[0]):
            activate(parent, f'/activate "{target.name}" profile', SimpleNamespace(show=Mock(), choose=Mock(side_effect=AssertionError("No migration prompt"))))
            assert parent._pending_profile_home == str(target)
            start = len(server.requests)
            # Use the prepared test interpreter; no package installs or live credentials.
            env = {k: v for k, v in os.environ.items()
                   if k in {"PATH", "LANG", "TZ", "TMPDIR", "SYSTEMROOT"}}
            env.update(HOME=str(tmp_path), SCI_HOME=str(target), SCI_DISABLE_LAZY_INSTALLS="1",
                       SCI_TEST_ISOLATION=str(home), NO_PROXY="127.0.0.1,localhost")
            if not native:
                env["OPENAI_API_KEY"] = "sk-fake-e2e"
            script = """
import ipaddress, runpy, socket
connect = socket.socket.connect
def loopback_only(sock, address):
    if isinstance(address, tuple) and not ipaddress.ip_address(address[0]).is_loopback:
        raise OSError('Fixture refuses non-loopback network access')
    return connect(sock, address)
socket.socket.connect = loopback_only
"""
            if mode == "legacy-cli":
                script += """
import contextlib, json, sys
with contextlib.redirect_stdout(sys.stderr):
    import sci_bootstrap
    from cli import SciCLI
    instance = SciCLI(toolsets=['terminal', 'file', 'skills'])
    assert instance._init_agent()
print(json.dumps({'kind': 'ready'}))
for text in ('hello', 'what skills are available?'):
    with contextlib.redirect_stdout(sys.stderr):
        assert instance._init_agent()
        result = instance.agent.run_conversation(text, conversation_history=instance.conversation_history,
                                                 task_id=instance.session_id)
        instance.conversation_history = result['messages']
    print(json.dumps({'kind': 'result', 'text': result['final_response'], 'failed': bool(result.get('failed'))}))
with contextlib.redirect_stdout(sys.stderr):
    instance.agent.close()
"""
            else:
                script += "runpy.run_module('sci_cli.science_profile_worker', run_name='__main__')\n"
            result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                                    env=env, input='{"kind":"turn","text":"hello"}\n'
                                    '{"kind":"turn","text":"what skills are available?"}\n{"kind":"close"}\n',
                                    text=True, capture_output=True, timeout=90)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            assert result.returncode == 0, result.stderr[-3000:]
            assert [e["kind"] for e in events] == ["ready", "result", "result"], (events, result.stderr[-3000:])
            assert all(not e["failed"] and e["text"] == "SCI fixture response" for e in events[1:])
            requests = [r["body"] for r in server.requests[start:] if r["kind"] == "main"]
            if native:
                assert all(r["auth"] == "Bearer sk-shared-profile-test" for r in server.requests[start:] if r["kind"] == "main")
                assert "sk-shared-profile-test" not in (target / ".env").read_text()
            assert len(requests) == 2
            systems = [[m for m in r["messages"] if m["role"] == "system"] for r in requests]
            assert systems[0] == systems[1]
            text = json.dumps(systems[0])
            assert "built by Boltzmann Labs" in text
            assert "hermes-agent.nousresearch.com" not in text
            assert "Do not load skills, browse, or run commands solely to introduce yourself" in text
            assert ("ANTIBODY_ONLY" in text) == (target.name == "antibody")
            assert ("MOLECULE_ONLY" in text) == (target.name == "molecule")
            assert "fixture" in text
            assert requests[0]["tools"] == requests[1]["tools"]
            names = {t["function"]["name"] for t in requests[0]["tools"]}
            assert "skill_view" in names
            assert ("terminal" in names) == native
        assert (home / "config.yaml").read_bytes() == before
        assert parent.agent.system_prompt == "cached" and parent.agent.tools == ["unchanged"]
        assert parent.conversation_history == [{"role": "user", "content": "main only"}]
