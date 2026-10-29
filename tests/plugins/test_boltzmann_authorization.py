"""Bundled connector authorization must precede discovery and every operation."""

import json
import shutil
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
import requests

from agent.secret_scope import set_multiplex_context, reset_multiplex_context
from gateway.run import _profile_runtime_scope
from sci_cli.callbacks import prompt_for_secret
from sci_cli.config import load_config, load_env, save_config, save_env_value
from sci_cli.plugins import PluginManager


@pytest.fixture
def auth_server(monkeypatch):
    state = {"revoked": False, "calls": []}
    real_request = requests.sessions.Session.request

    def local_request(session, method, url, *args, **kwargs):
        assert urlparse(url).hostname == "127.0.0.1", "Test refused a non-localhost request"
        return real_request(session, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", local_request)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["calls"].append(self.path)
            if urlparse(self.path).path == "/artifact.csv":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"id,value\nfixture-1,1\nfixture-2,2\n")
                return
            ok = self.headers.get("Authorization") == "Bearer " + state.get("accepted_key", "fixture-valid") and not state["revoked"]
            self.send_response(state.get("result_http", 200) if ok and self.path == "/result" else 200 if ok else 401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {"status": "success" if ok else "error"}
            if ok and self.path == "/result":
                payload["OutputData"] = {"fixture": {"download_link":
                    f"http://127.0.0.1:{self.server.server_port}/artifact.csv"}}
                payload.update(state.get("result_override", {}))
            self.wfile.write(json.dumps(payload).encode())

        def do_POST(self):
            state["calls"].append(self.path)
            assert self.headers.get("Authorization") == "Bearer " + state.get("accepted_key", "fixture-valid")
            if self.path == "/tool-log":
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                state.setdefault("diagnostic_requests", []).append(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"fixture_record": payload}).encode())
                return
            if self.path == "/upload":
                state["upload_bytes"] = self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": True, "fileDetails": {
                    "folderPath": state.get("upload_path", "fixture/water.xyz")}}).encode())
                return
            assert self.path == "/submit"
            state["submission"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(state.get("submit_http", 200))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state.get("submit_response", {"success": True, "docId": "fixture-job"})).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}/api/get-projects"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@contextmanager
def profile(home):
    home.mkdir(exist_ok=True)
    multiplex_token = set_multiplex_context(True)
    try:
        with _profile_runtime_scope(home, hydrate_secrets=False):
            yield
    finally:
        reset_multiplex_context(multiplex_token)


def discover(monkeypatch, endpoint):
    manager = PluginManager()
    manager.discover_and_load()
    loaded = manager._plugins["boltzmann"]
    assert not loaded.error, loaded.error
    module = loaded.module
    helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
    monkeypatch.setattr(helpers, "_AUTH_CHECK_URL", endpoint)
    return manager, module


def capture(manager, monkeypatch, value):
    cli = SimpleNamespace(agent=SimpleNamespace(system_prompt="cached-prefix", tools=[{"old": "tools"}]),
                          conversation_history=[{"role": "user", "content": "unchanged"}])
    cli._secret_capture_callback = lambda key, prompt, **kw: prompt_for_secret(cli, key, prompt, **kw)
    manager._cli_ref = cli
    monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _: value)
    from sci_cli.plugins import PluginContext
    loaded = manager._plugins["boltzmann"]
    onboarding = loaded.module.onboarding
    return onboarding.add_boltzmann(PluginContext(loaded.manifest, manager), ""), cli


def test_main_and_named_profile_credentials_resolve_without_fallback(tmp_path, monkeypatch, auth_server):
    """Main is the root, never profiles/default; failed validation must not claim a missing key."""
    from sci_cli.profiles import get_profile_dir, resolve_profile_env
    state, endpoint = auth_server
    main = tmp_path / ".sci"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(main))
    monkeypatch.setenv("BOLTZMANN_API_KEY", "inherited-key-must-not-be-used")
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    (main / "profiles").mkdir(parents=True)
    a, b = main / "profiles" / "a", main / "profiles" / "b"
    with profile(main):
        manager, module = discover(monkeypatch, endpoint)
        auth = sys.modules[module.__name__ + ".auth"]
        try:
            assert get_profile_dir("default") == main
            assert Path(resolve_profile_env("default")) == main
            for home, key in ((main, "fixture-main"), (a, "fixture-a"), (b, "fixture-b"),
                              (a, "fixture-a"), (main, "fixture-main")):
                with profile(home):
                    save_env_value("BOLTZMANN_API_KEY", key)
                    auth.authorize_saved_key()
                    state.update(accepted_key=key, revoked=False)
                    assert auth.current_key() == key
                    assert auth.require_authorized() == key
                    state["revoked"] = True
                    result = json.loads(module.tools.handle_boltzmann_status(job_name="fixture", doc_id="existing"))
                    assert "API key is configured" in result["error"]
                    assert str(home / ".env") in result["error"]
                    assert key not in result["error"]
            with profile(b):
                save_env_value("BOLTZMANN_API_KEY", "")
                calls = list(state["calls"])
                result = json.loads(module.tools.handle_boltzmann_status(job_name="fixture", doc_id="existing"))
                assert "No Boltzmann API key" in result["error"]
                assert str(b / ".env") in result["error"]
                assert state["calls"] == calls  # No main/env fallback, nor remote probe.
                assert not auth.available()
            assert auth.current_key() == "fixture-main"
            assert not (main / "profiles" / "default").exists()
            assert set(state["calls"]) == {"/api/get-projects"}
        finally:
            manager.unload()

    # With no profile activation or explicit SCI_HOME, native main uses the root .env.
    from sci_constants import get_sci_home
    with monkeypatch.context() as plain_launch:
        plain_launch.delenv("SCI_HOME", raising=False)
        assert get_sci_home() == main
        assert auth.current_key() == "fixture-main"


def test_diagnostic_lookup_resolves_collection_without_changing_job_or_profile(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(tmp_path / "a"):
        manager, module = discover(monkeypatch, endpoint)
        auth = sys.modules[module.__name__ + ".auth"]
        # Patch the globals actually bound by the real discovered handler.
        monkeypatch.setitem(module.tools.fetch_tool_log.__globals__, "_TOOL_LOG_URL",
                            endpoint.replace("/api/get-projects", "/tool-log"))
        try:
            for name in ("a", "b", "a"):
                with profile(tmp_path / name):
                    key = "fixture-" + name
                    save_env_value("BOLTZMANN_API_KEY", key)
                    auth.authorize_saved_key()
                    state["accepted_key"] = key
                    result = json.loads(module.tools.handle_boltzmann_fetch_tool_log(
                        job_name="Random_Antibody_Generation", experiment_id="fixture-" + name))
                    assert result["fixture_record"] == {
                        "collection": "AB_GEN", "experiment_id": "fixture-" + name}
                    for arguments in (
                        {"job_name": "Random_Antibody_Generation", "collection": "wrong"},
                        {"job_name": "unknown-job"},
                        {},
                    ):
                        previous = list(state["diagnostic_requests"])
                        result = json.loads(module.tools.handle_boltzmann_fetch_tool_log(
                            experiment_id="fixture-" + name, **arguments))
                        assert result["error"] and result["status"] == "not_started"
                        assert state["diagnostic_requests"] == previous
            # Existing keyword-based explicit collection calls remain supported.
            result = json.loads(module.tools.handle_boltzmann_fetch_tool_log(
                collection="AB_GEN", experiment_id="fixture-a"))
            assert result["fixture_record"]["collection"] == "AB_GEN"
            state["revoked"] = True
            previous = list(state["diagnostic_requests"])
            result = json.loads(module.tools.handle_boltzmann_fetch_tool_log(
                job_name="Random_Antibody_Generation", experiment_id="fixture-a"))
            assert result["authorization_required"]
            assert state["diagnostic_requests"] == previous
            assert set(state["calls"]) == {"/api/get-projects", "/tool-log"}
        finally:
            manager.unload()


def test_command_is_required_and_activation_is_deferred_and_profile_local(tmp_path, monkeypatch, auth_server, capsys):
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    with profile(a):
        save_config({"model": {"default": "keep-model"}, "display": {"skin": "mono"},
                     "platform_toolsets": {"cli": ["terminal", "no_mcp"]},
                     "agent": {"disabled_toolsets": ["boltzmann", "browser"]}})
        save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
        manager, module = discover(monkeypatch, endpoint)
        try:
            from sci_cli.commands import is_gateway_known_command
            from sci_cli.commands_platforms import telegram_bot_commands
            assert not is_gateway_known_command("add_boltzmann")
            assert "add_boltzmann" not in dict(telegram_bot_commands())
            from sci_cli.commands import resolve_command
            assert resolve_command("/add_boltzmann").cli_only
            assert not module.available()  # a preexisting key is not command approval
            assert not state["calls"]  # discovery never contacts the service
            assert not manager._plugin_skills
            from tools.registry import registry
            names = {schema["name"] for schema in module.SCHEMAS}
            assert not registry.get_definitions(names, quiet=True)
            for name in names:
                assert json.loads(getattr(module.tools, "handle_" + name)())["authorization_required"]
            assert not state["calls"]
            for value, outcome in (("", "CANCELLED"), ("invalid", "FAILED"), ("fixture-valid", "SAVED")):
                message, cli = capture(manager, monkeypatch, value)
                assert outcome in message
                assert load_env()["BOLTZMANN_API_KEY"] == "fixture-valid"
                assert cli.agent.system_prompt.encode() == b"cached-prefix"
                assert cli.agent.tools == [{"old": "tools"}]
                assert cli.conversation_history == [{"role": "user", "content": "unchanged"}]
                assert not manager._plugin_skills  # default never live-registers skills
                assert module.available() == (outcome == "SAVED")
            assert "next session" in message
            assert load_config()["model"]["default"] == "keep-model"
            assert load_config()["display"]["skin"] == "mono"
            assert load_config()["platform_toolsets"]["cli"] == ["terminal", "no_mcp", "boltzmann"]
            assert load_config()["agent"]["disabled_toolsets"] == ["browser"]
            with profile(b):
                save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                assert not module.available()  # same key, different home, no receipt
            assert module.available()  # A → B → A
        finally:
            manager.unload()
        fresh, fresh_module = discover(monkeypatch, endpoint)
        try:
            assert fresh_module.available()
            assert "boltzmann:tools" in fresh._plugin_skills
            assert fresh._plugins["boltzmann"].tools_registered
            skill = fresh._plugin_skills["boltzmann:tools"]["path"]
            assert skill.is_relative_to(Path(__file__).resolve().parents[2] / "plugins" / "boltzmann")
            catalog = json.loads((skill.parent / "references/tool-contracts.v1.json").read_text())
            for entry in catalog["modules"]:
                assert (skill.parent / "references" / entry["path"]).is_file()
            assert {d["function"]["name"] for d in registry.get_definitions(names, quiet=True)} == names
        finally:
            fresh.unload()
    output = capsys.readouterr()
    assert "fixture-valid" not in output.out + output.err
    assert set(state["calls"]) == {"/api/get-projects"}


def test_revocation_blocks_all_operations_including_status_and_downloads(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(tmp_path / "a"):
        manager, module = discover(monkeypatch, endpoint)
        try:
            message, _ = capture(manager, monkeypatch, "fixture-valid")
            assert "SAVED" in message
            tools = module.tools
            monkeypatch.setattr(tools, "fetch_status", lambda *a, **kw: {"status": "completed", "private": "result"})
            with profile(tmp_path / "b"):
                save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                assert json.loads(tools.handle_boltzmann_status(job_name="job", doc_id="doc"))["authorization_required"]
            assert json.loads(tools.handle_boltzmann_status(job_name="job", doc_id="doc"))["private"] == "result"
            state["revoked"] = True
            for schema in module.SCHEMAS:
                handler = getattr(tools, "handle_" + schema["name"])
                result = json.loads(handler(job_name="job", doc_id="doc", download_url="https://unused.invalid/file",
                                            output_folder=str(tmp_path / "must-not-exist")))
                assert result["authorization_required"] is True
                assert "private" not in result
            assert not (tmp_path / "must-not-exist").exists()
            save_env_value("BOLTZMANN_API_KEY", "")
            assert not module.available()
            assert json.loads(tools.handle_boltzmann_submit())["authorization_required"]
            assert set(state["calls"]) == {"/api/get-projects"}
        finally:
            manager.unload()


def test_fresh_authorized_connector_executes_fixture_job_without_local_plugin(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "fresh"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.delenv("conv_id", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(tmp_path / "fresh"):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert not module.available()
            message, _ = capture(manager, monkeypatch, "fixture-valid")
            assert "SAVED" in message
        finally:
            manager.unload()


        manager, module = discover(monkeypatch, endpoint)
        try:
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            base = endpoint.removesuffix("/api/get-projects")
            monkeypatch.setattr(helpers, "_SUBMIT_URL", base + "/submit")
            monkeypatch.setattr(helpers, "_FETCH_URL", base + "/result")
            inputs = {"n_samples": 20, "file_format": "csv"}
            submitted = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Random_Antibody_Generation", experiment_data=inputs,
                experiment_name="approved-fixture"))
            assert submitted["doc_id"] == "fixture-job"
            assert state["submission"] == {"job_name": submitted["job_name"],
                "experimentData": inputs, "experimentName": "approved-fixture"}
            status = json.loads(module.tools.handle_boltzmann_status(
                job_name=submitted["job_name"], doc_id=submitted["doc_id"]))
            result = json.loads(module.tools.handle_boltzmann_download(
                download_url=status["OutputData"]["fixture"]["download_link"],
                output_folder=str(tmp_path / "outputs")))
            assert Path(result["output_paths"][0]).read_text().splitlines() == [
                "id,value", "fixture-1,1", "fixture-2,2"]
            assert state["calls"].count("/submit") == 1
            assert set(state["calls"]) <= {"/api/get-projects", "/submit", "/result", "/artifact.csv"}
        finally:
            manager.unload()


def test_partial_file_preflight_upload_and_submit_with_real_profile_receipts(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    with profile(a):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            base = endpoint.removesuffix("/api/get-projects")
            monkeypatch.setattr(helpers, "_UPLOAD_URL", base + "/upload")
            monkeypatch.setattr(helpers, "_SUBMIT_URL", base + "/submit")
            # Onboarding can refresh discovery; patch the actual bound functions,
            # not a replacement module object left in sys.modules after that refresh.
            monkeypatch.setitem(module.tools.file_upload.__globals__, "_UPLOAD_URL", base + "/upload")
            monkeypatch.setitem(module.tools.submit_request.__globals__, "_SUBMIT_URL", base + "/submit")
            water = tmp_path / "water.xyz"
            water.write_text("3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n")
            args = {"local_path": str(water), "job_name": "Single_Point_Energy", "input_field": "molecule_path"}
            first = json.loads(module.tools.handle_boltzmann_upload(**args))
            assert first["approval_required"] and not first["validation"]["errors"]
            assert "/upload" not in state["calls"]
            uploaded = json.loads(module.tools.handle_boltzmann_upload(**args, allow_partial_validation=True))
            assert uploaded.get("status") == "uploaded", uploaded
            assert water.read_bytes() in state["upload_bytes"]
            payload = {"task_name": "water", "molecule_path": uploaded["s3_path"], "method": "B3LYP",
                       "basis": "def2-TZVP", "charge": 0, "spin_multiplicity": "1", "dispersion": "D3BJ"}
            preflight = sys.modules[module.__name__ + ".preflight"]
            original = preflight.preflight_submission("Single_Point_Energy", payload).as_dict()
            with profile(b):
                save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                other = preflight.preflight_submission("Single_Point_Energy", payload)
                assert any("no current-profile validation receipt" in w for w in other.warnings)
            assert preflight.preflight_submission("Single_Point_Energy", payload).as_dict() == original
            result = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Single_Point_Energy", experiment_data=payload, experiment_name="fixture-water",
                allow_partial_validation=True))
            assert result["status"] == "accepted" and result["validation"]["level"] == "partial"
            assert state["calls"].count("/submit") == 1
            assert state["submission"]["experimentData"] == payload
            invalid = dict(payload, spin_multiplicity=1)
            result = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Single_Point_Energy", experiment_data=invalid, experiment_name="fixture-water",
                allow_partial_validation=True))
            assert result["validation"]["errors"]
            assert state["calls"].count("/submit") == 1
        finally:
            manager.unload()


def test_binding_affinity_uses_authorized_connector_for_direct_and_uploaded_inputs(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(a))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    job = "global_binding_affinity"
    with profile(a):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            base = endpoint.removesuffix("/api/get-projects")
            monkeypatch.setitem(module.tools.file_upload.__globals__, "_UPLOAD_URL", base + "/upload")
            monkeypatch.setitem(module.tools.submit_request.__globals__, "_SUBMIT_URL", base + "/submit")
            source = tmp_path / "pairs.csv"
            source.write_text("SMILES,SEQUENCE\nfixture-smiles,fixture-sequence\n")
            state["upload_path"] = "fixture/pairs.csv"
            uploaded = json.loads(module.tools.handle_boltzmann_upload(
                local_path=str(source), job_name=job, input_field="input_csv", allow_partial_validation=True))
            assert uploaded["status"] == "uploaded", uploaded
            assert source.read_bytes() in state["upload_bytes"]
            payloads = ({"smiles": "fixture-smiles", "sequence": "fixture-sequence"},
                        {"input_csv": uploaded["s3_path"]})
            preflight = sys.modules[module.__name__ + ".preflight"]
            original = preflight.preflight_submission(job, payloads[1]).as_dict()
            with profile(b):
                save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                assert any("no current-profile validation receipt" in w
                           for w in preflight.preflight_submission(job, payloads[1]).warnings)
            assert preflight.preflight_submission(job, payloads[1]).as_dict() == original
            for payload in payloads:
                result = json.loads(module.tools.handle_boltzmann_submit(
                    job_name=job, experiment_data=payload, experiment_name="fixture-affinity",
                    allow_partial_validation=True))
                assert result["status"] == "accepted", result
                assert state["submission"] == {"job_name": job, "experimentData": payload,
                                               "experimentName": "fixture-affinity"}
            assert state["calls"].count("/submit") == len(payloads)
        finally:
            manager.unload()


def test_five_enzyme_tools_use_existing_profile_scoped_wire_path(tmp_path, monkeypatch, auth_server):
    import copy

    state, endpoint = auth_server
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(a))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(a):
        manager, module = discover(monkeypatch, endpoint)
        try:
            message, cli = capture(manager, monkeypatch, "fixture-valid")
            assert "SAVED" in message
            base = endpoint.removesuffix("/api/get-projects")
            for function, setting, route in ((module.tools.file_upload, "_UPLOAD_URL", "/upload"),
                                              (module.tools.submit_request, "_SUBMIT_URL", "/submit"),
                                              (module.tools.fetch_status, "_FETCH_URL", "/result")):
                monkeypatch.setitem(function.__globals__, setting, base + route)
            store = module.tools.ContractStore()
            preflight = sys.modules[module.__name__ + ".preflight"]
            for job in ("deepallo", "enzycontrol", "Enzyme_RFD3", "Catalytic_Geometry", "Mol_Probity"):
                payload = copy.deepcopy(store.tool(job)["examples"][0]["experiment_data"])
                # Synthetic shapes, never valid scientific jobs or production services.
                payload["input_path" if job != "enzycontrol" else "pdb_path"] = "fixture/input.pdb"
                for field, prop in store.file_fields(job).items():
                    if field not in payload:
                        continue
                    if field in {"input_path", "pdb_path"}:
                        data = b"ATOM      1  O   HOH A   1       0.000   0.000   0.000  1.00  0.00           O\nEND\n"
                        filename = field + ".pdb"
                    else:
                        values = {
                            "reaction_template": {"reaction_state": "fixture", "sources": ["fixture"], "checks": [{
                                "check_id": "fixture", "type": "distance", "rationale": "test shape only", "sources": ["fixture"],
                                "evidence_level": "user_defined", "atoms": [
                                    {"entity_type": "residue", "chain_id": "A", "residue_number": n, "atom_name": "CA"}
                                    for n in (1, 2)], "min": 1, "max": 2}]},
                            "template_binding": {"mapping_keys": {"fixture": {"chain_id": "A", "residue_number": 1}}},
                            "mapping_path": {"candidate": {"fixture": {"chain_id": "A", "residue_number": 1}}},
                        }
                        data = json.dumps(values[field]).encode()
                        filename = field + ".json"
                    local = tmp_path / filename
                    local.write_bytes(data)
                    state["upload_path"] = "fixture/" + filename
                    uploaded = json.loads(module.tools.handle_boltzmann_upload(
                        local_path=str(local), job_name=job, input_field=field,
                        experiment_data=payload, allow_partial_validation=True))
                    assert uploaded["status"] == "uploaded", uploaded
                    assert data in state["upload_bytes"]
                    payload[field] = uploaded["s3_path"]
                # Preserve a worker run label separately from the outer RFD3 routing name.
                if job == "Enzyme_RFD3":
                    payload["job_name"] = "fixture-rfd3-worker-run"
                # Exercise inline file_or_value objects through real preflight, not just schemas.
                if job == "Mol_Probity":
                    payload.update(execution_mode="validation", quality_thresholds={"max_clashscore": 0})
                before = preflight.preflight_submission(job, payload).as_dict()
                with profile(b):
                    result = json.loads(module.tools.handle_boltzmann_submit(
                        job_name=job, experiment_data=payload, experiment_name="fixture", allow_partial_validation=True))
                    assert result["authorization_required"]
                    assert any("no current-profile validation receipt" in warning
                               for warning in preflight.preflight_submission(job, payload).warnings)
                assert preflight.preflight_submission(job, payload).as_dict() == before
                count = state["calls"].count("/submit")
                result = json.loads(module.tools.handle_boltzmann_submit(
                    job_name=job, experiment_data=payload, experiment_name="fixture", allow_partial_validation=True))
                assert result["status"] == "accepted", result
                assert state["submission"] == {"experimentData": payload, "job_name": job, "experimentName": "fixture"}
                assert not {"user_id", "tokenid", "experiment_id"} & payload.keys()
                if job == "Enzyme_RFD3":
                    assert state["submission"]["job_name"] == "Enzyme_RFD3"
                    assert state["submission"]["experimentData"]["job_name"] == "fixture-rfd3-worker-run"
                else:
                    assert "job_name" not in payload
                status = json.loads(module.tools.handle_boltzmann_status(job_name=job, doc_id="fixture-job"))
                assert status["status"] == "success", status
                assert state["calls"].count("/submit") == count + 1
                assert cli.agent.system_prompt == "cached-prefix"
                assert cli.agent.tools == [{"old": "tools"}]
            assert not manager._plugin_skills  # No live prompt/skill injection.
        finally:
            manager.unload()


def test_ligand_pharmacophore_upload_submit_and_receipts_are_profile_scoped(tmp_path, monkeypatch, auth_server):
    """Use native plugin discovery and localhost transport, never a paid backend."""
    state, endpoint = auth_server
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(a))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    job = "ligand_pharmacophore"
    payload = {"smiles_file": "fixture/training.csv", "validation_file": "fixture/validation.csv",
               "min_features": 2, "max_features": 5, "percentage": 0.5,
               "n_conformers": 20, "features": ["hb acceptor", "aromatic ring"]}
    with profile(a):
        manager, module = discover(monkeypatch, endpoint)
        try:
            auth = sys.modules[module.__name__ + ".auth"]
            preflight = sys.modules[module.__name__ + ".preflight"]
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            base = endpoint.removesuffix("/api/get-projects")
            for setting, suffix in (("_UPLOAD_URL", "/upload"), ("_SUBMIT_URL", "/submit"),
                                    ("_FETCH_URL", "/result")):
                monkeypatch.setattr(helpers, setting, base + suffix)
            source = tmp_path / "ligands.csv"
            source.write_text("SMILES\nCCO\n")
            validation = tmp_path / "validation.csv"
            validation.write_text("SMILES,LABELS\nCCO,active\nCCN,inactive\n")
            args = {"local_path": str(source), "job_name": job, "input_field": "smiles_file"}
            unauthorized = json.loads(module.tools.handle_boltzmann_upload(**args))
            assert unauthorized["authorization_required"]
            assert "/upload" not in state["calls"]
            for index, home in enumerate((a, b, a)):
                with profile(home):
                    save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                    auth.authorize_saved_key()
                    if index < 2:
                        before = preflight.preflight_submission(job, payload)
                        assert any("no current-profile validation receipt" in w for w in before.warnings)
                        for field in ("smiles_file", "validation_file"):
                            state["upload_path"] = payload[field]
                            input_file = source if field == "smiles_file" else validation
                            upload = dict(args, input_field=field, local_path=str(input_file))
                            blocked = json.loads(module.tools.handle_boltzmann_upload(**upload))
                            assert blocked.get("approval_required"), blocked
                            approved = json.loads(module.tools.handle_boltzmann_upload(
                                **upload, allow_partial_validation=True))
                            assert approved["status"] == "uploaded", approved
                            assert input_file.read_bytes() in state["upload_bytes"]
                    after = preflight.preflight_submission(job, payload)
                    assert not after.errors
                    assert not any("no current-profile validation receipt" in w for w in after.warnings)
                    assert preflight.decision(after, False)["approval_required"]
                    assert preflight.decision(after, True) is None
            bad = tmp_path / "wrong.csv"
            bad.write_text("wrong_column\nCCO\n")
            invalid = json.loads(module.tools.handle_boltzmann_upload(
                **dict(args, local_path=str(bad)), allow_partial_validation=True))
            assert invalid["status"] == "not_started"
            missing_labels = json.loads(module.tools.handle_boltzmann_upload(
                **dict(args, input_field="validation_file"), allow_partial_validation=True))
            assert missing_labels["status"] == "not_started", missing_labels
            assert any("LABELS" in error for error in missing_labels["validation"]["errors"])
            assert state["calls"].count("/upload") == 4
            submit = {"job_name": job, "experiment_data": payload, "experiment_name": "Local fixture only"}
            blocked = json.loads(module.tools.handle_boltzmann_submit(**submit))
            assert blocked["approval_required"] and "/submit" not in state["calls"]
            accepted = json.loads(module.tools.handle_boltzmann_submit(**submit, allow_partial_validation=True))
            assert accepted["doc_id"] == "fixture-job", accepted
            assert state["submission"]["job_name"] == job
            assert state["submission"]["experimentData"] == payload
            module.tools.handle_boltzmann_status(job_name=job, doc_id="fixture-job")
            assert state["calls"].count("/submit") == 1
            assert source.read_text() == "SMILES\nCCO\n"
            assert validation.read_text() == "SMILES,LABELS\nCCO,active\nCCN,inactive\n"
        finally:
            manager.unload()


def test_enzyme_upload_enforces_headers_and_profile_scoped_current_rules(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(a))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(a):
        manager, module = discover(monkeypatch, endpoint)
        try:
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            auth = sys.modules[module.__name__ + ".auth"]
            preflight = sys.modules[module.__name__ + ".preflight"]
            base = endpoint.removesuffix("/api/get-projects")
            monkeypatch.setattr(helpers, "_UPLOAD_URL", base + "/upload")
            source = tmp_path / "enzymes.csv"
            original = b"Sequence_ID,Sequences\nenzyme-1,MKT\n"
            corrected = b"Seq_id,Sequences\nenzyme-1,MKT\n"
            source.write_bytes(original)
            args = {"local_path": str(source), "job_name": "Enzymes", "input_field": "dataPath",
                    "experiment_data": {"property_name": ["enzyme_solubility"]}}
            save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
            auth.authorize_saved_key()
            rejected = json.loads(module.tools.handle_boltzmann_upload(**args, allow_partial_validation=True))
            assert rejected["status"] == "not_started", rejected
            assert rejected["validation"]["errors"]
            assert "/upload" not in state["calls"] and "/submit" not in state["calls"]
            assert source.read_bytes() == original

            # A reviewed copy, not a silent rewrite of the user's original input.
            reviewed = tmp_path / "enzymes-reviewed.csv"
            reviewed.write_bytes(corrected)
            args["local_path"] = str(reviewed)
            payload = {"dataPath": "fixture/enzymes.csv", "property_name": ["enzyme_solubility"]}
            state["upload_path"] = payload["dataPath"]
            for home in (a, b, a):
                with profile(home):
                    save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                    auth.authorize_saved_key()
                    if home == b:
                        unvalidated = preflight.preflight_submission("Enzymes", payload)
                        assert any("no current-profile validation receipt" in w for w in unvalidated.warnings)
                    if home == b or "/upload" not in state["calls"]:
                        uploaded = json.loads(module.tools.handle_boltzmann_upload(**args))
                        assert uploaded["status"] == "uploaded", uploaded
                        assert not uploaded["validation"]["errors"]
                        assert not uploaded["validation"]["warnings"]
                        assert corrected in state["upload_bytes"]
                    report = preflight.preflight_submission("Enzymes", payload)
                    assert not report.errors and not report.warnings, report.as_dict()
                    assert source.read_bytes() == original and reviewed.read_bytes() == corrected

            # Receipts from before the stricter header rule must be revalidated.
            from sci_cli.plugins_state import PluginState
            old_store = preflight.ContractStore()
            old_rule = old_store.files["Enzymes"]["files"]["dataPath"]
            old_rule.pop("columns", None)
            key = preflight._receipt_key("Enzymes", "dataPath", payload["dataPath"])
            receipt = PluginState("boltzmann").get(key)
            receipt["contract"] = preflight._contract_digest(old_store, "Enzymes")
            PluginState("boltzmann").set(key, receipt)
            stale = preflight.preflight_submission("Enzymes", payload)
            assert any("validate and upload again" in error for error in stale.errors)
            assert preflight.decision(stale, True)["status"] == "not_started"
            assert state["calls"].count("/upload") == 2 and "/submit" not in state["calls"]
        finally:
            manager.unload()


def test_service_diagnostics_are_safe_and_status_failures_do_not_resubmit(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(tmp_path / "a"):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            base = endpoint.removesuffix("/api/get-projects")
            monkeypatch.setattr(helpers, "_SUBMIT_URL", base + "/submit")
            monkeypatch.setattr(helpers, "_FETCH_URL", base + "/result")
            state.update(submit_http=422, submit_response={"detail": [{"msg": "Invalid input column; fixture-valid https://example.invalid/?token=private"}]})
            result = helpers.submit_request({"fixture": True}, "fixture", "approved", token="fixture-valid")
            assert "Invalid input column" in result["error"]
            assert "fixture-valid" not in json.dumps(result) and "token=private" not in json.dumps(result)
            assert result["stage"] == "submit" and result["safe_to_retry"] is False
            state["result_override"] = {"status": "failed", "error": "Worker rejected the input columns"}
            failed = helpers.fetch_status("fixture", "fixture-job", token="fixture-valid", max_wait=2)
            assert failed["status"] == "failed" and "columns" in failed["error"]
            state["result_override"] = {"status": "running"}
            pending = helpers.fetch_status("fixture", "fixture-job", token="fixture-valid", max_wait=0.03, watch_time=0.01)
            assert pending["timeout"] and pending["status"] in {"running", "unknown"}
            state["revoked"] = True
            inaccessible = helpers.fetch_status("fixture", "fixture-job", token="fixture-valid", max_wait=2)
            assert inaccessible["status"] == "unknown" and inaccessible["authorization_required"]
            assert state["calls"].count("/submit") == 1
        finally:
            manager.unload()


def test_submit_preserves_service_diagnostics_without_claiming_a_job_outcome(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    home = tmp_path / "a"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(home):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            monkeypatch.setitem(module.tools.submit_request.__globals__, "_SUBMIT_URL",
                                endpoint.removesuffix("/api/get-projects") + "/submit")
            traceback = ("Traceback (most recent call last):\n" + "  credit calculator frame\n" * 120
                         + "ValueError: fixture credit calculation failure")
            backend_error = "Missing required column(s): Seq_id, Sequence / Sequences, SMILES in catpred.csv"
            for count, http in enumerate((500, 422, 401), start=1):
                state.update(submit_http=http, submit_response={"status": "failed", "success": False,
                             "error": backend_error,
                             "message": "Failed to calculate credits", "info": {
                                 "info": "fixture input could not be priced", "message": traceback,
                                 "diagnostics": ["fixture-valid https://example.invalid/?token=private"]}})
                result = json.loads(module.tools.handle_boltzmann_submit(
                    job_name="Cat_Pred", experiment_data={"input_path": "fixture/pairs.csv"},
                    experiment_name="fixture-negative", allow_partial_validation=True))
                assert result.get("message") == "Failed to calculate credits", result
                assert result["service_error"] == backend_error
                assert result["success"] is False
                if http != 401:
                    assert result["error"] == backend_error
                assert result["info"]["info"] == "fixture input could not be priced"
                assert result["info"]["message"] == traceback
                assert result["status"] == "unknown" and result["service_status"] == "failed"
                assert result["authorization_required"] is (http == 401)
                assert result["safe_to_retry"] is False and "doc_id" not in result
                assert "http_status" not in result and "status_code" not in result
                assert "fixture-valid" not in json.dumps(result) and "token=private" not in json.dumps(result)
                assert state["calls"].count("/submit") == count
            state.update(submit_http=500, submit_response={"message": "Failed to calculate credits"})
            result = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Cat_Pred", experiment_data={"input_path": "fixture/pairs.csv"},
                experiment_name="fixture-no-traceback", allow_partial_validation=True))
            assert result["message"] == "Failed to calculate credits" and "info" not in result
            assert "service_status" not in result and result["status"] == "unknown"
            state["submit_response"] = {}
            result = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Cat_Pred", experiment_data={"input_path": "fixture/pairs.csv"},
                experiment_name="fixture-empty-response", allow_partial_validation=True))
            assert "HTTP " not in result["error"] and "http_status" not in result
            assert result["status"] == "unknown" and result["safe_to_retry"] is False
            assert state["calls"].count("/submit") == 5 and "/result" not in state["calls"]
        finally:
            manager.unload()


def test_schema_rejection_preserves_field_errors_without_echoing_secrets(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    home = tmp_path / "schema-errors"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(home):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            monkeypatch.setattr(helpers, "_SUBMIT_URL", endpoint.removesuffix("/api/get-projects") + "/submit")
            state.update(submit_http=400, submit_response={
                "message": "Schema validation failed", "status": "failed",
                "errors": [{"path": "flexible_residues", "message": "fixture field rejected",
                            "value": {"private": "reflected-input-secret"}}],
                "details": {"message": "fixture-valid https://example.invalid/?signature=private",
                            "tokenid": "another-secret"},
                "validation_errors": [{"loc": ["body", "example"], "msg": "fixture invalid",
                                       "input": "reflected-input-secret"}],
            })
            result = helpers.submit_request({"fixture": True}, "fixture", "diagnostic-check", token="fixture-valid")
            assert result["message"] == "Schema validation failed"
            assert result["errors"][0]["path"] == "flexible_residues"
            assert result["errors"][0]["message"] == "fixture field rejected"
            assert result["validation_errors"][0]["loc"] == ["body", "example"]
            assert "details" in result
            for secret in ("fixture-valid", "signature=private", "another-secret", "reflected-input-secret"):
                assert secret not in json.dumps(result)
            assert result["status"] == "unknown" and result["service_status"] == "failed"
            assert result["safe_to_retry"] is False and "doc_id" not in result
            assert state["calls"].count("/submit") == 1
        finally:
            manager.unload()


def test_flexible_docking_uploads_csv_and_rejects_inline_smiles(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    home = tmp_path / "flexible-docking"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(home):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            base = endpoint.removesuffix("/api/get-projects")
            monkeypatch.setitem(module.tools.submit_request.__globals__, "_SUBMIT_URL", base + "/submit")
            monkeypatch.setitem(module.tools.file_upload.__globals__, "_UPLOAD_URL", base + "/upload")
            payload = {"target_name": "fixture", "processed_pdb": "fixture/receptor.pdb",
                       "center_x": "0", "center_y": "0", "center_z": "0",
                       "max_radius_size": "10", "exhaustivness": "8", "upload_sdf": "True",
                       "flexible_residues": ["ALA1"], "smiles": "CCO"}
            rejected = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Vina_Flexible_Docking", experiment_data=payload,
                experiment_name="fixture", allow_partial_validation=True))
            assert rejected["status"] == "not_started" and "/submit" not in state["calls"]
            assert any("smiles" in e for e in rejected["validation"]["errors"])
            csv = tmp_path / "ligands.csv"
            csv.write_text("fixture_column\nCCO\n")
            original = csv.read_bytes()
            state["upload_path"] = "fixture/ligands.csv"
            uploaded = json.loads(module.tools.handle_boltzmann_upload(
                local_path=str(csv), job_name="Vina_Flexible_Docking", input_field="smiles",
                experiment_data=payload, allow_partial_validation=True))
            assert uploaded["status"] == "uploaded"
            assert any("columns are not documented" in w for w in uploaded["validation"]["warnings"])
            payload["smiles"] = uploaded["s3_path"]
            accepted = json.loads(module.tools.handle_boltzmann_submit(
                job_name="Vina_Flexible_Docking", experiment_data=payload,
                experiment_name="fixture", allow_partial_validation=True))
            assert accepted["status"] == "accepted"
            assert state["submission"]["experimentData"] == payload
            assert state["calls"].count("/upload") == state["calls"].count("/submit") == 1
            assert csv.read_bytes() == original
        finally:
            manager.unload()


def test_graph_ga_preserves_selected_global_property_in_http_request(tmp_path, monkeypatch, auth_server):
    """Non-default properties must reach the Node envelope without substitution."""
    state, endpoint = auth_server
    home = tmp_path / "global-property-forwarding"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(home):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            monkeypatch.setitem(module.tools.submit_request.__globals__, "_SUBMIT_URL",
                                endpoint.removesuffix("/api/get-projects") + "/submit")
            for count, name in enumerate(("Solubility", "Lipophilicity"), start=1):
                payload = {"smiles": "CCO", "n_mols": 1, "n_steps": 1,
                           "global_models": [{"name": name, "min_threshold": -4, "max_threshold": 0.4}],
                           "custom_models": []}
                before = json.loads(json.dumps(payload))
                result = json.loads(module.tools.handle_boltzmann_submit(
                    job_name="Lead_Generation_Graph_GA", experiment_data=payload,
                    experiment_name="fixture-property-routing"))
                assert result["status"] == "accepted", result
                assert state["submission"] == {"experimentData": before,
                                               "job_name": "Lead_Generation_Graph_GA",
                                               "experimentName": "fixture-property-routing"}
                assert payload == before
                assert state["calls"].count("/submit") == count
        finally:
            manager.unload()


def test_status_preserves_nested_worker_diagnostics_and_running_messages(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    home = tmp_path / "a"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(home):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            monkeypatch.setitem(module.tools.fetch_status.__globals__, "_FETCH_URL",
                                endpoint.removesuffix("/api/get-projects") + "/result")
            monkeypatch.setitem(module.tools.fetch_status.__globals__, "_tool_timeout", lambda *args: 0.04)
            cause = "stat: path should be string, bytes, os.PathLike or integer, not NoneType"
            traceback = ('Traceback (most recent call last):\n  File "/worker/fpocket_main.py", line 20\n'
                         + "  worker frame\n" * 180 + "TypeError: " + cause)
            for http in (200, 404):
                state.update(result_http=http, result_override={"status": "failed", "message": "job failed",
                             "info": {"info": cause, "message": traceback,
                                      "diagnostics": [{"message": "fixture-valid https://example.invalid/?token=private"}]}})
                result = json.loads(module.tools.handle_boltzmann_status(job_name="fpocket", doc_id="fixture-job"))
                assert result["status"] == "failed" and result["message"] == "job failed", result
                assert result["info"]["info"] == cause and result["info"]["message"] == traceback
                assert "fixture-valid" not in json.dumps(result) and "token=private" not in json.dumps(result)
                assert "http_status" not in result and "status_code" not in result
                assert result["job_name"] == "fpocket" and result["doc_id"] == "fixture-job"
                state["result_override"] = {"status": "running", "message": "job is still in execution"}
                running = json.loads(module.tools.handle_boltzmann_status(job_name="fpocket", doc_id="fixture-job"))
                assert running["status"] == "running" and running["message"] == "job is still in execution"
                assert running["timeout"] and "error" not in running and "info" not in running
                assert "http_status" not in running and "status_code" not in running
            assert "/submit" not in state["calls"]
        finally:
            manager.unload()


def test_status_transport_failures_do_not_fabricate_job_states(tmp_path, monkeypatch, auth_server):
    state, endpoint = auth_server
    home = tmp_path / "a"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(home):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            helpers = sys.modules[module.__name__ + ".nodeapi_helpers"]
            monkeypatch.setattr(helpers, "_FETCH_URL", endpoint.removesuffix("/api/get-projects") + "/result")
            for http, body in ((404, {"status": "error", "message": "Route not found"}),
                               (404, {"status": "success"}), (404, {"status": None}),
                               (500, {"status": "running", "message": "Proxy failed"}),
                               (404, {"status": "unexpected", "message": "Unknown response"})):
                state.update(result_http=http, result_override=body)
                result = helpers.fetch_status("fpocket", "fixture-job", token="fixture-valid", max_wait=1)
                assert result["status"] == "unknown" and result["safe_to_retry"] is False
                assert "http_status" not in result and "status_code" not in result
                assert "HTTP " not in result["error"]
            state.update(result_http=404, result_override={"status": "failed", "message": "job failed"}, revoked=True)
            result = helpers.fetch_status("fpocket", "fixture-job", token="fixture-valid", max_wait=1)
            assert result["authorization_required"] and result["status"] == "unknown"
            assert "/submit" not in state["calls"]
        finally:
            manager.unload()


def test_file_upload_discovery_and_fresh_multi_artifact_results(tmp_path, monkeypatch, auth_server):
    """Exercise the real connector against localhost only; no scientific worker runs."""
    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    with profile(tmp_path / "a"):
        manager, module = discover(monkeypatch, endpoint)
        try:
            assert "SAVED" in capture(manager, monkeypatch, "fixture-valid")[0]
            base = endpoint.removesuffix("/api/get-projects")
            for func, setting, suffix in [(module.tools.file_upload, "_UPLOAD_URL", "/upload"),
                                          (module.tools.submit_request, "_SUBMIT_URL", "/submit"),
                                          (module.tools.fetch_status, "_FETCH_URL", "/result")]:
                monkeypatch.setitem(func.__globals__, setting, base + suffix)
            # Registration formerly failed before file inspection. A generic short
            # format fixture is sufficient; it is not a valid experiment sample.
            source = tmp_path / "format-only.fasta"
            source.write_text(">format-fixture\nACGU\n")
            state["upload_path"] = "fixture/format-only.fasta"
            upload_args = dict(local_path=str(source), job_name="rna_siRNA_gen", input_field="input_fasta")
            before = json.loads(module.tools.handle_boltzmann_upload(**upload_args))
            assert before["approval_required"] and not before["validation"]["errors"]
            assert "/upload" not in state["calls"]
            uploaded = json.loads(module.tools.handle_boltzmann_upload(**upload_args, allow_partial_validation=True))
            assert uploaded["status"] == "uploaded"
            assert source.read_bytes() in state["upload_bytes"]
            accepted = json.loads(module.tools.handle_boltzmann_submit(
                job_name="rna_siRNA_gen", experiment_name="localhost-connector-test",
                experiment_data={"input_fasta": uploaded["s3_path"]}, allow_partial_validation=True))
            assert accepted["status"] == "accepted"
            assert state["calls"].count("/submit") == 1
            paths = []
            for revision in (1, 2):
                links = [f"{base}/artifact.csv?artifact={i}&revision={revision}" for i in (1, 2)]
                state["result_override"] = {"OutputData": {"fixture": {"download_link": links}}}
                result = json.loads(module.tools.handle_boltzmann_status(job_name="rna_siRNA_gen", doc_id="fixture-job"))
                assert result["OutputData"]["fixture"]["download_link"] == links
                assert result["doc_id"] == "fixture-job"
                for link in links:
                    downloaded = json.loads(module.tools.handle_boltzmann_download(
                        download_url=link, output_folder=str(tmp_path / "artifacts")))
                    assert downloaded["status"] == "downloaded"
                    paths.extend(downloaded["output_paths"])
            assert state["calls"].count("/result") == 2  # terminal URLs are refreshed
            assert len(set(paths)) == len(paths)  # identical basenames never overwrite
            assert all(Path(path).read_text().startswith("id,value") for path in paths)
            assert state["calls"].count("/submit") == 1  # polling/downloads never resubmit
            rejected = json.loads(module.tools.handle_boltzmann_upload(
                **dict(upload_args, input_field="undeclared_field"), allow_partial_validation=True))
            assert rejected["stage"] == "validation" and rejected["status"] == "not_started"
            assert not rejected["uploaded"] and state["calls"].count("/upload") == 1
        finally:
            manager.unload()


@pytest.mark.parametrize("user_override", [False, True], ids=["bundled", "user-plugin"])
def test_execution_policy_is_authorized_profile_local_and_frozen(tmp_path, monkeypatch, auth_server, user_override):
    from agent.conversation_loop import _restore_or_build_system_prompt
    from agent.system_prompt import _frozen_plugin_prompt_sections
    from run_agent import AIAgent
    from sci_cli import plugins

    state, endpoint = auth_server
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "a"))
    monkeypatch.delenv("SCI_BUNDLED_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    if user_override:
        shutil.copytree(Path(__file__).resolve().parents[2] / "plugins/boltzmann", a / "plugins/boltzmann",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def agent(session):
        return AIAgent(api_key="test-key", base_url="https://openrouter.ai/api/v1",
                       model="test/model", provider="openrouter", platform="cli",
                       enabled_toolsets=["skills", "boltzmann"], quiet_mode=True,
                       skip_context_files=True, skip_memory=True, session_id=session)

    with profile(a):
        save_config({"plugins": {"enabled": ["boltzmann"]}})
        manager, module = discover(monkeypatch, endpoint)
        monkeypatch.setattr(plugins, "_plugin_manager", manager)
        try:
            old = agent("before-boltzmann-authorization")
            _restore_or_build_system_prompt(old, None, [])
            old_prompt = old._cached_system_prompt.encode()
            old_tools = json.dumps(old.tools, sort_keys=True)
            assert not _frozen_plugin_prompt_sections(old)
            message, _ = capture(manager, monkeypatch, "fixture-valid")
            assert "SAVED" in message
            _restore_or_build_system_prompt(old, None, [{"role": "user", "content": "existing turn"}])
            assert old._cached_system_prompt.encode() == old_prompt
            assert json.dumps(old.tools, sort_keys=True) == old_tools
            assert not _frozen_plugin_prompt_sections(old)
        finally:
            manager.unload()

        manager, module = discover(monkeypatch, endpoint)
        monkeypatch.setattr(plugins, "_plugin_manager", manager)
        try:
            if user_override:
                assert Path(manager._plugins["boltzmann"].manifest.path).is_relative_to(a / "plugins")
            fresh = agent("after-boltzmann-authorization")
            _restore_or_build_system_prompt(fresh, None, [])
            snapshot = _frozen_plugin_prompt_sections(fresh)
            policy = next(section.content for section in snapshot if section.id == "boltzmann.execution")
            assert "boltzmann:tools" in policy
            assert "protein-antibody-generation.md" in policy
            assert "explicit" in policy and "restart" in policy.lower()
            assert "fixture-valid" not in policy
            # Inventory requests must reach scientific metadata, not stop at
            # the deferred connector schemas. Also catches an oversized section
            # being dropped by the real prompt-section renderer.
            assert "references/tool-contracts.v1.json" in policy
            assert "grouped by domain and module title" in policy
            assert "not the five connector helpers" in policy
            from model_tools import get_tool_definitions
            definitions = get_tool_definitions(enabled_toolsets=["skills", "boltzmann"], quiet_mode=True,
                                               skip_tool_search_assembly=True)
            names = {schema["function"]["name"] for schema in definitions}
            assert {schema["name"] for schema in module.SCHEMAS} <= names
            for definition in definitions:
                function = definition["function"]
                if function["name"] in {schema["name"] for schema in module.SCHEMAS}:
                    assert function["parameters"]["properties"]  # Discoverable helpers must be callable.
            skill = manager._plugin_skills["boltzmann:tools"]["path"]
            instructions = skill.read_text()
            assert "## Listing Scientific Tools" in instructions
            assert "`module_id`" in instructions and "`display_name`" in instructions
            assert "account-entitlement" in instructions
            registry = json.loads((skill.parent / "references/tool-contracts.v1.json").read_text())
            antibody = next(entry for entry in registry["modules"]
                            if entry["path"] == "modules/protein-antibody-generation.md")
            assert (skill.parent / "references" / antibody["path"]).is_file()
            assert "Random_Antibody_Generation" in (skill.parent / "references" / antibody["path"]).read_text()
            fresh_prompt = fresh._cached_system_prompt.encode()
            with profile(b):
                save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
                assert not manager.render_system_prompt_sections({})  # same key, no approval in B
            assert manager.render_system_prompt_sections({}) == list(snapshot)  # A → B → A
            save_env_value("BOLTZMANN_API_KEY", "")
            assert not manager.render_system_prompt_sections({})
            assert not module.available()
            _restore_or_build_system_prompt(fresh, None, [{"role": "user", "content": "existing turn"}])
            assert fresh._cached_system_prompt.encode() == fresh_prompt
            assert _frozen_plugin_prompt_sections(fresh) == snapshot
        finally:
            manager.unload()
    assert set(state["calls"]) == {"/api/get-projects"}  # no scientific jobs or remote services
