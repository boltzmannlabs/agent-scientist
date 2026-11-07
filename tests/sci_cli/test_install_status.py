"""The installer distinguishes absent configuration from a broken status check."""
import pytest

from sci_cli import install_status


@pytest.mark.parametrize('ready', [False, True])
def test_configuration_status_is_read_only(monkeypatch, capsys, ready):
    from sci_cli import main

    monkeypatch.setattr(main, '_has_any_provider_configured', lambda: ready)
    assert install_status.main() == (0 if ready else 3)
    text = capsys.readouterr().out
    assert ('connectivity has not been tested' in text) == ready
    assert ('sci setup' in text) != ready


def test_status_failure_is_not_reported_as_missing_credentials(monkeypatch):
    from sci_cli import main

    def broken():
        raise OSError('controlled unreadable configuration')

    monkeypatch.setattr(main, '_has_any_provider_configured', broken)
    with pytest.raises(OSError, match='controlled unreadable configuration'):
        install_status.main()
