"""Saved main-model effort follows the selected profile and validates before writing."""

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException


def test_main_effort_assignment_is_atomic_profile_scoped_and_does_not_show_thinking(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.model_switch import ModelSwitchResult
    from sci_cli.web_models import ModelAssignment
    from sci_cli.web_routers import models

    root = tmp_path / '.sci'
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(root))
    homes = {name: root / 'profiles' / name for name in ('a', 'b')}
    for home in (root, *homes.values()):
        home.mkdir(parents=True, exist_ok=True)
        atomic_config_replace(home / 'config.yaml', {
            'model': {'provider': 'openai', 'default': 'fixture-old'},
            'agent': {'reasoning_effort': 'low'}, 'display': {'show_reasoning': False},
        })
    monkeypatch.setattr(models, '_dashboard_code_skew_guard', lambda: None)
    monkeypatch.setattr(models, '_prepare_main_assignment', lambda cfg, provider, model, *_:
        ('', ModelSwitchResult(success=True, new_model=model, target_provider=provider)))

    def apply(name, **extra):
        return asyncio.run(models.set_model_assignment(ModelAssignment(
            scope='main', provider='openai', model='fixture-new', confirm_expensive_model=True, **extra), profile=name))

    assert apply('a', reasoning_effort='high')['ok']
    assert apply('b', reasoning_effort='medium')['ok']
    assert apply('a')['ok']  # An omitted field preserves A's explicit setting.
    for name, expected in [('a', 'high'), ('b', 'medium')]:
        cfg = read_user_config_raw(homes[name] / 'config.yaml')
        assert cfg['agent']['reasoning_effort'] == expected
        assert cfg['model']['default'] == 'fixture-new'
        assert cfg['display']['show_reasoning'] is False
    assert read_user_config_raw(root / 'config.yaml')['agent']['reasoning_effort'] == 'low'
    before = (homes['a'] / 'config.yaml').read_bytes()
    with pytest.raises(HTTPException) as error:
        apply('a', reasoning_effort='invalid-effort')
    assert error.value.status_code == 400
    assert (homes['a'] / 'config.yaml').read_bytes() == before
