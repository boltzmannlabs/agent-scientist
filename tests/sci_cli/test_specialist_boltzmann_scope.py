"""Specialist integration packages cannot borrow another profile's authorization."""
from pathlib import Path
from types import SimpleNamespace

from agent.specialist_store import Specialist, save
from agent.specialist_runtime import capture, resolve
from sci_cli.native_profile_creation import profile_scope
from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS
from sci_cli.specialist_capabilities import boltzmann_ready, tool_menu, skill_menu, BOLTZMANN_PACKAGE


def test_boltzmann_package_uses_real_profile_receipt_a_b_a(tmp_path, monkeypatch):
    from plugins.boltzmann.auth import authorize_saved_key
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('a', 'b')]
    for home in homes:
        home.mkdir()
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    (homes[0] / '.env').write_text('BOLTZMANN_API_KEY=fixture-not-a-real-key\n')
    helpers = dict.fromkeys(BOLTZMANN_WORKFLOW_TOOLS, 'fixture metadata')
    # Hold metadata constant: only the real owning-profile credential/receipt may grant access.
    monkeypatch.setattr('model_tools._select_tool_names', lambda *a, **k: set(helpers))
    token = set_multiplex_context(True)
    try:
        for home, expected in ((homes[0], True), (homes[1], False), (homes[0], True)):
            with profile_scope(home):
                if expected and not boltzmann_ready():
                    authorize_saved_key()  # local fixture receipt; no authentication request or scientific job
                assert boltzmann_ready() is expected
                menu, _ = tool_menu(helpers, ())
                assert (BOLTZMANN_PACKAGE in menu) is expected
                try:
                    save(Specialist('reviewer', 'Review', tools=tuple(helpers), automatic=True))
                except FileExistsError:
                    pass
                parent = SimpleNamespace(enabled_toolsets=[], disabled_toolsets=[], platform='cli')
                capture(parent)
                parent._specialist_parent_tools = frozenset(helpers)
                _, policy = resolve(parent, {'specialist': 'reviewer'})
                assert policy.tools == (frozenset(helpers) if expected else frozenset())
                assert policy.unavailable_tools == (frozenset() if expected else frozenset(helpers))
    finally:
        reset_multiplex_context(token)


def test_disabled_base_skill_cannot_be_added_through_module_menu(monkeypatch):
    monkeypatch.setattr('sci_cli.specialist_capabilities.boltzmann_ready', lambda: True)
    def no_catalog_read():
        raise AssertionError('A disabled skill must not be offered through module aliases')
    monkeypatch.setattr('sci_cli.specialist_capabilities.modules', no_catalog_read)
    menu, _, resources = skill_menu({}, dict.fromkeys(BOLTZMANN_WORKFLOW_TOOLS), Specialist('reviewer', 'Review'))
    assert 'boltzmann:tools' not in menu and not resources
