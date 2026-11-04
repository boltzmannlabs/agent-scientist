"""Real SDK routing with a canned loopback response; not actual LLM reasoning.

Run through the installed host's scripts/run_tests.sh, not the focused branch's
tree (which does not contain the host SDK). Every profile/definition is temporary.
"""
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from specialist.test_native import isolated_home, model_fixture
from specialist.fixtures import source, canned_answer
from specialist.advisor import prepare, ANSWER_FIELDS
from pilot.native import NativeDecisionDriver, parent_factory, RoutingError
from pilot.runner import digest


def test_actual_native_main_and_named_child_routing(isolated_home, monkeypatch):
    from agent.specialist_store import Specialist, save
    from sci_cli.config import atomic_config_replace
    monkeypatch.setattr("agent.model_metadata.get_model_context_length", lambda *a, **k: 131072)
    monkeypatch.setattr("agent.context_compressor.get_model_context_length", lambda *a, **k: 131072)
    raw = json.loads((Path(__file__).parents[1] / "specialist/definition.json").read_text())
    definition = Specialist.parse(raw)
    frozen = {k: raw[k] for k in ("name", "purpose", "instructions", "output", "tools", "skills", "skill_files", "sources", "children",
                                "max_iterations", "timeout_seconds")}
    packet = prepare(source())["packet"]
    packet["specialist_definition"] = frozen
    packet["advice_fields"] = sorted(ANSWER_FIELDS)
    packet["engineering_fixture_padding"] = "ARTIFICIAL_TRANSPORT_DATA_NO_MOLECULE_WAS_SCORED " * 1000
    packet["context_limits"] = {"maximum_assignment_chars": 262144}
    packet["input_digest"] = digest({k: v for k, v in packet.items() if k != "input_digest"})
    answer = canned_answer(packet["input_digest"])
    with model_fixture(answer) as (url, calls):
        atomic_config_replace(isolated_home / "config.yaml", {
            "model": {"default": "fixture-model", "provider": "custom", "base_url": url, "context_length": 131072},
            "tool_search": {"enabled": "off"}, "memory": {"enabled": False},
            "delegation": {"max_iterations": 3, "child_timeout_seconds": 120}, "agent": {"max_iterations": 3}})
        saved = save(replace(definition, enabled=True, needs_review=False))
        options = {"model": "fixture-model", "provider": "custom", "api_key": "local-fixture-key",
                   "base_url": url, "api_mode": "chat_completions"}
        driver = NativeDecisionDriver(parent_factory(options), {"model": "fixture-model", "provider": "custom"}, response_source="fixture")
        with pytest.raises(RoutingError, match="exceeds"):
            driver.choose("base_algorithm", {**packet, "context_limits": {"maximum_assignment_chars": 24000}})
        assert not calls
        main = driver.choose("base_algorithm", packet)
        specialist = driver.choose("base_algorithm_specialist", packet)
        assert main["advice"] == specialist["advice"] == answer
        assert not main["runtime"]["specialist_invoked"]
        assert specialist["runtime"]["specialist_invoked"]
        assert specialist["runtime"]["specialist_name"] == "smallmol-investigation"
        assert main["evidence_kind"] == specialist["evidence_kind"] == "fixture"
        assert main["runtime"]["transmitted_assignment_chars"] > 24000
        assert main["runtime"]["transmitted_assignment_chars_limit"] == 262144
        assert len(calls) >= 2 and all(not p.get("tools") for p in calls)
        for call in calls:
            transmitted = "\n".join(m["content"] for m in call.get("messages", []) if isinstance(m.get("content"), str))
            assert transmitted.count(raw["instructions"]) == 1
            assert "scientific_role_binding" in transmitted and packet["input_digest"] in transmitted
            assert packet["engineering_fixture_padding"] in transmitted
        count = len(calls)
        changed = save(replace(saved, max_iterations=saved.max_iterations + 1), expected_revision=saved.revision)
        with pytest.raises(RoutingError, match="frozen scientific role"):
            driver.choose("base_algorithm_specialist", packet)
        assert len(calls) == count
        saved = save(replace(changed, max_iterations=saved.max_iterations), expected_revision=changed.revision)
        save(replace(saved, enabled=False), expected_revision=saved.revision)
        with pytest.raises(RoutingError, match="did not complete"):
            driver.choose("base_algorithm_specialist", packet)
        assert len(calls) == count
