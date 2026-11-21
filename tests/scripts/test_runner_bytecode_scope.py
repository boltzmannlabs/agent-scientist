"""Package-source protection must not disable bytecode behavior in unrelated tests."""
import pytest


@pytest.mark.parametrize('contributed', [False, True])
def test_runner_limits_bytecode_suppression_to_contributed_packages(tmp_path, monkeypatch, contributed):
    from scripts import run_tests_parallel as runner

    monkeypatch.delenv('PYTHONDONTWRITEBYTECODE', raising=False)
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    root = tmp_path / 'repo'
    directory = root / ('subagent-catalog/sample/tests' if contributed else 'tests')
    directory.mkdir(parents=True)
    (directory / 'helper.py').write_text('VALUE = 7\n', encoding='utf-8')
    case = directory / 'test_probe.py'
    case.write_text(
        'import os, subprocess, sys\nfrom pathlib import Path\n'
        'def test_child_cache():\n'
        f'    assert bool(os.environ.get("PYTHONDONTWRITEBYTECODE")) == {contributed!r}\n'
        f'    directory = Path({str(directory)!r})\n'
        '    result = subprocess.run([sys.executable, "-c", "import helper; assert helper.VALUE == 7"],\n'
        '        cwd=directory, capture_output=True, text=True, encoding="utf-8", errors="replace")\n'
        '    assert result.returncode == 0, result.stderr\n'
        f'    assert bool(list((directory / "__pycache__").glob("helper.*.pyc"))) == {not contributed!r}\n',
        encoding='utf-8')
    _, code, output, summary, _ = runner._run_one_file_once(case, ['-q'], root, 30)
    assert code == 0, output
    assert summary.get('passed') == 1, output
