"""Package CLI dispatch and embedded release catalogs work without runtime-state copying."""
from pathlib import Path
from types import SimpleNamespace
import base64
import json
import shutil

from sci_cli.specialist_commands import dispatch
from sci_cli.native_profile_creation import profile_scope
from sci_cli.config import atomic_config_replace
from agent.specialist_store import load


class UI:
    def __init__(self, answers=()):
        self.answers, self.messages = iter(answers), []
    def show(self, value):
        self.messages.append(str(value))
    def ask(self, *args, **kwargs):
        return next(self.answers)
    def choose(self, question, choices):
        answer = next(self.answers)
        assert answer in choices, (question, answer, choices)
        return answer



def fixture_catalog(tmp_path, monkeypatch):
    import sci_cli.subagent_package_catalog as catalog
    from sci_cli.subagent_package_schema import validate
    from sci_cli.subagent_package_io import LOCK, checksums
    source = tmp_path / 'fixture-catalog/table-reviewer'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent', source)
    manifest, files, digest = validate(source)
    files[LOCK] = json.dumps(checksums(files)).encode()
    snapshot = tmp_path / 'fixture-catalog.json'
    snapshot.write_text(json.dumps({'table-reviewer': {'manifest': manifest, 'digest': digest,
        'files': {name: base64.b64encode(data).decode() for name, data in files.items()}}}))
    monkeypatch.setattr(catalog, 'CATALOG', source.parent)
    monkeypatch.setattr(catalog, 'SNAPSHOT', snapshot)
    return catalog

def test_package_cli_picker_installs_into_selected_native_profile_without_switching(tmp_path, monkeypatch):
    fixture_catalog(tmp_path, monkeypatch)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    main, target = tmp_path / '.sci', tmp_path / '.sci/profiles/destination'
    monkeypatch.setenv('SCI_HOME', str(main))
    for home in (main,target):
        home.mkdir(parents=True,exist_ok=True)
        atomic_config_replace(home / 'config.yaml',{'platform_toolsets':{'cli':['file','skills','delegation']}})
    cli = SimpleNamespace(agent=None)
    with profile_scope(main):
        ui = UI(['destination','Prepare package','Save and enable for the next conversation'])
        dispatch(cli, '/subagent package install catalog:table-reviewer', ui)
        assert load('table-reviewer',target).package_info['state']=='ready',ui.messages
        assert not (main / 'subagents/table-reviewer.json').exists()
        from sci_constants import get_sci_home
        assert get_sci_home()==main
        for removed in ('export', 'seal', 'validate'):
            check = UI()
            dispatch(cli, '/subagent package ' + removed + ' unused', check)
            assert any('These preparation slash commands are not provided' in line for line in check.messages)
            assert load('table-reviewer',target).package_info['state']=='ready'
        menu = UI(['Catalog','Done'])
        dispatch(cli, '/subagent package', menu)


def test_embedded_wheel_catalog_matches_tree_and_rejects_tampered_metadata(tmp_path, monkeypatch):
    import sci_cli.subagent_package_catalog as catalog
    from sci_cli.subagent_package_schema import validate
    import pytest
    assert catalog.catalog() == {}  # No example specialist is shipped.
    catalog = fixture_catalog(tmp_path, monkeypatch)
    direct = catalog.catalog()
    snapshot = tmp_path / 'catalog.json'
    snapshot.write_bytes(catalog.SNAPSHOT.read_bytes())
    monkeypatch.setattr(catalog,'CATALOG',tmp_path / 'no-source-checkout')
    monkeypatch.setattr(catalog,'SNAPSHOT',snapshot)
    assert set(catalog.catalog())==set(direct)
    for key, row in direct.items():
        with catalog.package(key) as root:
            manifest, _, digest = validate(root)
            assert manifest==row['manifest'] and digest==row['digest']
    rows=json.loads(snapshot.read_text())
    key=next(iter(rows))
    rows[key]['files']['instructions.md']=base64.b64encode(b'Tampered').decode()
    snapshot.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        with catalog.package(key):
            pytest.fail('Tampered embedded package was exposed')
