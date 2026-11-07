"""Native Windows menu requirements select only targets with a locked wheel."""
from pathlib import Path
import tomllib
from urllib.parse import urlparse

from packaging.requirements import Requirement
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def test_native_menu_dependency_matches_platform_and_lock():
    manifest = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    requirements = [Requirement(value) for value in manifest['project']['dependencies']]
    requirement = next(value for value in requirements if value.name == 'windows-curses')
    lock = tomllib.loads((ROOT / 'uv.lock').read_text())
    package = next(value for value in lock['package'] if value['name'] == requirement.name)
    assert package['version'] in requirement.specifier
    assert requirement.marker.evaluate({'sys_platform': 'win32', 'platform_machine': 'AMD64', 'python_version': '3.14'})
    for platform, machine in [('linux', 'x86_64'), ('darwin', 'arm64'), ('win32', 'ARM64')]:
        assert not requirement.marker.evaluate({'sys_platform': platform, 'platform_machine': machine, 'python_version': '3.14'})
    tags = set()
    for wheel in package['wheels']:
        assert wheel['hash'].startswith('sha256:')
        tags.update(parse_wheel_filename(Path(urlparse(wheel['url']).path).name)[3])
    assert any(tag.interpreter == 'cp314' and tag.platform == 'win_amd64' for tag in tags)
