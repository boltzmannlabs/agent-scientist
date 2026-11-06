"""Actual SDK admission-chain canary; no model, network or scientific jobs.

Run ONLY through the SDK's scripts/run_tests.sh. Set SMALLMOL_GATE_FIXTURE_JSON
before launching it to a private JSON file containing db_path, assignment_id and
environment_source. The fixture must be prepared by the qualified RDKit scoring
interpreter (for example from workflow.test_admission.AdmissionTests.setUp).
The SDK interpreter only reopens the existing environment DB; it does not compute
molecular metrics. Missing external fixture is an explicit skip, not qualification.
"""
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from specialist.test_native import isolated_home  # noqa: F401; scoped SDK/network fixture


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


@pytest.fixture
def native_gate(isolated_home, tmp_path, request):
    source = os.environ.get("SMALLMOL_GATE_FIXTURE_JSON")
    if not source:
        cached = Path(request.config.getini('cache_dir')) / 'smallmol-gate-fixture.json'
        source = str(cached) if cached.is_file() else None
    if not source:
        pytest.skip("Prepare private SMALLMOL_GATE_FIXTURE_JSON with the qualified scoring interpreter")
    fixture = json.loads(Path(source).read_text())
    environment = Path(fixture["environment_source"]).resolve()
    if not (environment / "leadopt_env" / "core.py").is_file():
        raise ValueError("Fixture environment_source must name the real leadopt_env src directory")
    sys.path.insert(0, str(environment))
    from leadopt_env.core import CampaignStore
    from workflow.session import WorkflowSession
    from workflow.admission import AdmissionGate, install
    from sci_cli.plugins import PluginContext, PluginManifest, get_plugin_manager

    # SQLite backup includes committed WAL data and leaves the supplied fixture
    # unchanged. All canary mutations, if any, stay in the test's own database.
    copied = tmp_path / "campaign.sqlite3"
    original = Path(fixture["db_path"]).resolve()
    with closing(sqlite3.connect("file:" + quote(str(original)) + "?mode=ro", uri=True)) as read:
        with closing(sqlite3.connect(copied)) as write:
            read.backup(write)
    store = CampaignStore(copied)
    session = WorkflowSession(store, fixture["assignment_id"])
    manager = get_plugin_manager()
    manager.discover_and_load()
    context = PluginContext(PluginManifest(name="smallmol-gate-canary", source="user"), manager)
    gate = AdmissionGate(session)
    handles = [install(context, session)]
    calls = []
    try:
        yield context, gate, session, store, handles, calls
    finally:
        for handle in reversed(handles):
            if handle is not None:
                handle.dispose()


def test_actual_dispatch_allows_current_report_and_blocks_writes_and_foreign_campaign(native_gate):
    context, gate, session, store, handles, calls = native_gate
    from model_tools import handle_function_call

    def actual_environment_handler(args, **kwargs):
        calls.append(deepcopy(args))
        return json.dumps(store.dispatch(args["operation"], args["campaign_id"], args.get("payload")))

    schema = {"name": "leadopt_campaign", "description": "Real environment fixture handler for SDK admission qualification",
              "parameters": {"type": "object", "properties": {
                  "operation": {"type": "string"}, "campaign_id": {"type": "string"},
                  "payload": {"type": "object"}}, "required": ["operation", "campaign_id"]}}
    handle = context.register_tool(name="leadopt_campaign", toolset="smallmol_gate_test",
                                   schema=schema, handler=actual_environment_handler)
    assert handle is not None, "Canary must own its actual environment-handler registration"
    handles.append(handle)
    args = {"operation": "report", "campaign_id": session.campaign_id}
    expected = session.report()
    result = decoded(handle_function_call("leadopt_campaign", args,
        enabled_tools=["leadopt_campaign"], session_id="smallmol-native-gate-canary"))
    assert result["task_digest"] == expected["task_digest"]
    assert calls == [args]

    for request in ({"operation": "record_batch", "campaign_id": session.campaign_id, "payload": {}},
                    {"operation": "report", "campaign_id": "FOREIGN_CAMPAIGN_FIXTURE"}):
        denied = decoded(handle_function_call("leadopt_campaign", request,
            enabled_tools=["leadopt_campaign"], session_id="smallmol-native-gate-canary"))
        assert denied["status"] == "blocked"
        assert denied["stage"] == "workflow_admission"
        assert denied["downstream_called"] is False
        assert calls == [args]


def test_actual_middleware_chain_never_reaches_terminal_for_invalid_science_or_internal_fault(native_gate, monkeypatch):
    context, gate, session, store, handles, calls = native_gate
    from sci_cli.middleware import run_tool_execution_middleware
    from pilot.bridge import JOB_NAME

    library = session.spec["libraries"][0]
    correct = {"job_name": JOB_NAME, "input_field": "library_path", "local_path": library["csv_path"],
               "experiment_data": {**deepcopy(session.spec["objective"]["generation_parameters"]),
                                   "ref_mol": session.spec["reference"]["representation"]}}

    def terminal(payload):
        calls.append(deepcopy(payload))
        return {"error": "TEST_ONLY: the terminal should never be reached"}

    wrong_job = deepcopy(correct); wrong_job["job_name"] = "OTHER_JOB_FIXTURE"
    wrong_objective = deepcopy(correct)
    wrong_objective["experiment_data"]["global_models"][0]["max_threshold"] = 4
    for request in (wrong_job, wrong_objective):
        denied = decoded(run_tool_execution_middleware("boltzmann_upload", request, terminal))
        assert denied["status"] == "blocked"
        assert denied["stage"] == "workflow_admission"
        assert denied["downstream_called"] is False
        assert calls == []

    def broken_report():
        raise RuntimeError("TEST_FIXTURE: local evidence-store failure before dispatch")
    monkeypatch.setattr(session, "report", broken_report)
    denied = decoded(run_tool_execution_middleware("boltzmann_upload", correct, terminal))
    assert denied["status"] == "blocked"
    assert denied["stage"] == "workflow_admission"
    assert denied["downstream_called"] is False
    assert calls == []
