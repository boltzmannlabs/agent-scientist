"""Portable Boltzmann dependencies authenticate only in recipient private scope, never by parent fallback."""
import json
from pathlib import Path
from types import SimpleNamespace
import shutil

from sci_cli.subagent_package_install import install
from sci_cli.subagent_package_io import seal
from sci_cli.config import atomic_config_replace
from agent.specialist_extensions import extension_home, capability_scope
from agent.specialist_runtime import capture, resolve
from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def show(self, value):
        self.messages.append(str(value))
    def choose(self, question, choices):
        answer = next(self.answers)
        assert answer in choices, (question,answer,choices)
        return answer


def test_boltzmann_package_private_auth_without_parent_key_and_no_cross_profile_fallback(tmp_path, monkeypatch):
    import sci_yaml as yaml
    from sci_cli import callbacks
    monkeypatch.setattr(Path,'home',lambda:tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    monkeypatch.setenv('SCI_HOME',str(a))
    for home in (a,b):
        home.mkdir(); atomic_config_replace(home / 'config.yaml',{'platform_toolsets':{'cli':['file','skills','delegation']}})
    package=tmp_path / 'package'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent',package)
    manifest=yaml.safe_load((package / 'manifest.yaml').read_text())
    manifest['dependencies']=[{'id':'boltzmann','kind':'boltzmann','modules':[]}]
    manifest['tools']+=list(BOLTZMANN_WORKFLOW_TOOLS)
    (package / 'manifest.yaml').write_text(yaml.safe_dump(manifest));seal(package)
    # Only the external authentication transport is stubbed: real credential storage,
    # authorization receipt, plugin registration and runtime permission checks run.
    checked=[]
    class Response:
        status_code = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def json(self):
            return {'status': 'success', 'success': True}
        def iter_content(self, chunk_size=8192):
            yield json.dumps(self.json()).encode()
    def authenticate_transport(url, **kwargs):
        key = (kwargs.get('json') or {}).get('apiToken')
        if key is None:
            key = kwargs.get('headers', {}).get('Authorization', '').removeprefix('Bearer ')
        assert key == 'fixture-boltz-key'
        checked.append(key)
        return Response()
    monkeypatch.setattr('plugins.boltzmann.nodeapi_helpers.requests.get', authenticate_transport)
    monkeypatch.setattr(callbacks,'prompt_for_secret',lambda *a,**k:{'success':True,'value':'fixture-boltz-key'})
    item=install(package,a,SimpleNamespace(agent=None),UI(['Prepare package','Configure private authorization',
             'Enter new key for this profile','Validate key','Save and enable for the next conversation']))
    assert item.package_info['state']=='ready' and checked==['fixture-boltz-key']
    assert not (a / '.env').exists()
    from sci_cli.specialist_capabilities import boltzmann_ready
    assert not boltzmann_ready()
    with capability_scope(extension_home(item)):
        assert boltzmann_ready()
    parent=SimpleNamespace(enabled_toolsets=['file','skills','delegation'],disabled_toolsets=[],platform='cli')
    capture(parent);parent._specialist_parent_tools=frozenset({'read_file','delegate_task','skill_view','skills_list'})
    _, policy=resolve(parent,{'specialist':item.name})
    assert set(BOLTZMANN_WORKFLOW_TOOLS)<=policy.tools
    from sci_cli.native_profile_creation import profile_scope
    with profile_scope(b):
        assert not boltzmann_ready()
    assert not boltzmann_ready()
