"""Foundation records and native skill installation, without scientific execution."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_skill_bundles_are_loadable_and_contracts_reject_incomplete_claims(tmp_path):
    from sci_cli.omics_foundation import bundles
    from tools.skills_hub_models import _parse_frontmatter
    from tools.skills_guard import scan_skill
    from jsonschema import Draft202012Validator, ValidationError

    rendered = list(bundles())
    assert len({b.name for b in rendered}) == len(rendered)
    for bundle in rendered:
        directory = tmp_path / bundle.name
        directory.mkdir()
        for name, content in bundle.files.items():
            file = directory / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
        metadata = _parse_frontmatter(bundle.files["SKILL.md"])
        assert metadata["name"] == bundle.name
        assert len(metadata["description"]) <= 60 and metadata["description"].endswith(".")
        assert scan_skill(directory).verdict != "dangerous"
        schema = json.loads(bundle.files["references/contracts.schema.json"])
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator({**schema, "$ref": "#/$defs/EvidenceClaim"})
        valid = {"claim": "A possible association", "type": "hypothesis", "support": ["artifact:review"],
                 "limitations": ["Not causal evidence"], "confidence_rationale": "Exploratory observation"}
        validator.validate(valid)
        with pytest.raises(ValidationError):
            validator.validate({**valid, "support": []})
        with pytest.raises(ValidationError):
            validator.validate({**valid, "type": "proven"})
        run = Draft202012Validator({**schema, "$ref": "#/$defs/RunRecord"})
        run.validate({"run_id": "r1", "inputs": [{"input_id": "f1", "checksum": None}],
                      "software_versions": {}, "reference_versions": {}, "parameters": {},
                      "status": "blocked", "output_ids": []})
        with pytest.raises(ValidationError):
            run.validate({"run_id": "r1", "status": "succeeded"})


@pytest.mark.parametrize("action", ["Add foundation skills", "Keep current setup", "Cancel", "scan_failure"])
def test_reviewed_upgrade_preserves_user_state_and_is_profile_scoped(tmp_path, monkeypatch, action):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.profiles import create_profile
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.omics_foundation import offer_foundation, bundles
    from sci_cli.skill_add import Cancelled
    from tools.skills_tool import skill_view, _find_all_skills
    from tools.skills_guard import ScanResult

    main = tmp_path / "science-root"
    main.mkdir()
    monkeypatch.setenv("SCI_HOME", str(main))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *_: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *_: None)
    atomic_config_replace(main / "config.yaml", {"model": {"provider": "openai-codex", "default": "fixture"}})
    home = create_profile("omics", no_skills=True, no_alias=True)
    other = create_profile("other", no_skills=True, no_alias=True)
    names = [b.name for b in bundles()]
    custom = home / "skills" / names[0] / "SKILL.md"
    custom.parent.mkdir(parents=True)
    custom.write_text(f"---\nname: {names[0]}\ndescription: Private edited instructions.\n---\nUser edits stay private.\n")
    config = {"platform_toolsets": {"cli": []}, "plugins": {"enabled": []}, "mcp_servers": {},
              "skills": {"disabled": [names[0]]}, "unrelated": {"setting": "retain"}}
    atomic_config_replace(home / "config.yaml", config)
    for name in ("SOUL.md", "workspace/private.txt", "memories/MEMORY.md"):
        target = home / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("User private contents")
    before = {name: (home / name).read_bytes() for name in ("SOUL.md", "workspace/private.txt", "memories/MEMORY.md", ".env")}
    main_before = (main / "config.yaml").read_bytes()
    ui = SimpleNamespace(show=Mock(), choose=Mock(return_value=action))
    if action == "Cancel":
        ui.choose.side_effect = Cancelled()
        with pytest.raises(Cancelled):
            offer_foundation(home, ui)
    elif action == "scan_failure":
        ui.choose.return_value = "Add foundation skills"
        monkeypatch.setattr("tools.skills_guard.scan_skill", lambda *a, **kw:
                            ScanResult("fixture", "community", "community", "dangerous"))
        with pytest.raises(ValueError, match="blocked by scan"):
            offer_foundation(home, ui)
    else:
        offer_foundation(home, ui)
    assert before == {name: (home / name).read_bytes() for name in before}
    assert (main / "config.yaml").read_bytes() == main_before
    assert "User edits stay private" in custom.read_text()
    saved = read_user_config_raw(home / "config.yaml")
    assert saved["skills"] == config["skills"] and saved["unrelated"] == config["unrelated"]
    if action == "Add foundation skills":
        assert saved["platform_toolsets"]["cli"] == ["skills"]
        for scope in (home, other, home):
            with profile_scope(scope):
                visible = {s["name"] for s in _find_all_skills()}
                assert (names[-1] in visible) == (scope == home)
                assert names[0] not in visible
                if scope == home:
                    assert "Provenance" in skill_view(names[-1])
        ui.choose.reset_mock()
        offer_foundation(home, ui)
        ui.choose.assert_not_called()
    else:
        assert saved == config
        assert not (home / "skills" / names[-1]).exists()
