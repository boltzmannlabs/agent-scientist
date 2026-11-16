"""Built-in skill discovery and installed package execution without a plugin."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('name', ['agri-formulation-workflow', 'agri-models-and-design', 'agri-evidence-and-data', 'formulation-results'])
def test_builtin_agricultural_skills_sync_and_load_without_plugin(tmp_path, name):
    from sci_constants import set_sci_home_override, reset_sci_home_override
    from tools.skills_sync import sync_skills
    from tools.skills_tool import skill_view
    token = set_sci_home_override(tmp_path / name)
    try:
        sync_skills(quiet=True)
        loaded = json.loads(skill_view(name, allow_setup=False))
        assert loaded['success'], loaded
        assert not (tmp_path / name / 'plugins' / 'agriformulations').exists()
    finally:
        reset_sci_home_override(token)


def test_installed_package_default_workspace_stays_with_owning_profile(tmp_path):
    from tools.environments.local import served_profile_child_env
    homes = [tmp_path / 'a', tmp_path / 'b']
    request = tmp_path / 'request.json'

    def call(home, value):
        request.write_text(json.dumps(value))
        response = subprocess.run(
            [sys.executable, '-I', '-m', 'agri_tool', '--request-file', str(request)],
            cwd=tmp_path, env=served_profile_child_env(target_home=home, inherit_credentials=False),
            capture_output=True, text=True, timeout=30, check=True)
        return json.loads(response.stdout)

    created = call(homes[0], {'operation': 'project', 'action': 'create', 'payload': {'name': 'Profile A'}})
    assert created['status'] == 'completed', created
    other = call(homes[1], {'operation': 'project', 'project_id': created['project_id']})
    assert other['status'] == 'error', other
    loaded = call(homes[0], {'operation': 'project', 'project_id': created['project_id']})
    assert loaded['result']['brief']['name'] == 'Profile A'
    models = call(homes[1], {'operation': 'catalogue', 'action': 'models'})
    from agriformulations.rnd.simulation_catalog import catalogue
    assert {m['key'] for m in models['result']['models']} == {m['key'] for m in catalogue()}
