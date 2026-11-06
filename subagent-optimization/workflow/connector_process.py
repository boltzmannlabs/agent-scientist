"""Private process transport to the owning profile's EXISTING SDK wrappers.

This is not another scientific client. The isolated reasoning/scoring process
passes a single approved call to the existing host interpreter and dispatcher.
Authorization remains in the original profile; no credential files are copied.
No retries occur. A timeout or missing receipt is an unknown operation outcome.
Importing this module needs only the standard library, not RDKit or the SDK.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


TOOLS = frozenset({'boltzmann_upload', 'boltzmann_submit', 'boltzmann_status', 'boltzmann_download'})
SECRET_FIELDS = frozenset({'api_key', 'apikey', 'authorization', 'access_token', 'refresh_token',
                           'password', 'secret', 'cookie', 'cookies', 'bearer_token', 'token',
                           'api_token', 'auth_token', 'client_secret', 'private_key', 'session_token'})


class ProcessOutcomeUnknown(RuntimeError):
    """No qualified return; do not repeat a possibly dispatched operation."""


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _clean_arguments(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace('-', '_') if isinstance(key, str) else ''
            if (not isinstance(key, str) or normalized in SECRET_FIELDS
                    or normalized.endswith(('_api_key', '_access_token', '_refresh_token', '_secret', '_password'))):
                raise ValueError('Credentials must remain in the owning profile, not process arguments')
            _clean_arguments(item)
    elif isinstance(value, list):
        for item in value:
            _clean_arguments(item)
    _json(value)


def _private_write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(_json(value) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def _environment(owner_home):
    env = dict(os.environ)
    # Remove the isolated caller's profile/activation overrides, including test
    # activation. The absolute interpreter below is selected deliberately.
    for key in list(env):
        if key.startswith(('SCI_', '__SCI_')) or key in {'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'}:
            env.pop(key)
    env.update(SCI_HOME=str(owner_home), SCI_RUNTIME_DIR=str(owner_home / 'tools'),
               SCI_DISABLE_LAZY_INSTALLS='1', PYTHONDONTWRITEBYTECODE='1')
    return env


class OwningHostDispatcher:
    def __init__(self, host_root, interpreter, owner_home, private_directory, *, timeout_seconds=120):
        self.host_root = Path(host_root).expanduser().resolve()
        self.interpreter = Path(interpreter).expanduser().absolute()
        self.owner_home = Path(owner_home).expanduser().resolve()
        raw = Path(private_directory).expanduser().absolute()
        if any(p.is_symlink() for p in (raw, *raw.parents)):
            raise ValueError('Private transport paths must not traverse symlinks')
        self.private_directory = raw.resolve()
        publication = Path(__file__).resolve().parents[2]
        if self.private_directory.is_relative_to(publication) or self.private_directory.is_relative_to(self.host_root):
            raise ValueError('Keep private request/receipt files outside source repositories')
        if not self.host_root.is_dir() or not self.owner_home.is_dir() or not self.interpreter.is_file():
            raise ValueError('Existing SDK root, interpreter and owning profile are required')
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 600:
            raise ValueError('Use a positive bounded process timeout')
        self.timeout_seconds = timeout_seconds
        self.private_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.private_directory, 0o700)

    def __call__(self, tool_name, args):
        if tool_name not in TOOLS:
            raise ValueError('Only the four existing Boltzmann connector wrappers are available')
        return self._run('tool', tool_name, args)

    def validate(self, stage, args):
        if stage not in {'upload', 'submit'}:
            raise ValueError('Only existing upload/submission validation is supported')
        return self._run('validate', stage, args)

    def _run(self, operation, name, args):
        if not isinstance(args, dict):
            raise ValueError('Connector arguments must be a JSON object')
        _clean_arguments(args)
        folder = Path(tempfile.mkdtemp(prefix='connector-', dir=self.private_directory))
        request, response, log = folder / 'request.json', folder / 'response.json', folder / 'process.log'
        _private_write(request, {'operation': operation, 'name': name, 'arguments': deepcopy(args),
                                 'session_id': 'smallmol-owning-host-' + uuid.uuid4().hex})
        command = [str(self.interpreter), '-B', str(Path(__file__).resolve()), '--worker',
                   '--host-root', str(self.host_root), '--owner-home', str(self.owner_home),
                   '--request', str(request), '--response', str(response)]
        try:
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                result = subprocess.run(command, cwd=self.host_root, env=_environment(self.owner_home),
                                        stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=self.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            raise ProcessOutcomeUnknown('Owning-host call timed out; preserve private intent and reconcile without automatic retry') from None
        except Exception:
            raise ProcessOutcomeUnknown('Owning-host process did not return a qualified receipt; original outcome is unknown') from None
        if result.returncode != 0 or not response.is_file() or response.is_symlink():
            raise ProcessOutcomeUnknown('Owning-host process exited without a qualified receipt; original outcome is unknown')
        try:
            envelope = json.loads(response.read_text())
            _json(envelope)
            if not isinstance(envelope, dict) or envelope.get('ok') is not True or 'result' not in envelope:
                raise ValueError('No successful envelope')
        except Exception:
            raise ProcessOutcomeUnknown('Owning-host response is missing or unusable; reconcile the original call before repeating it') from None
        return envelope['result']


def _execute(request, host_root):
    """Normal SDK call/validation; no AIAgent bootstrap or dependency setup."""
    sys.path.insert(0, str(host_root))
    operation, name, args = request['operation'], request['name'], request['arguments']
    if operation == 'validate':
        job = args['job_name']
        if name == 'upload':
            from plugins.boltzmann.contracts import ContractStore
            from plugins.boltzmann.file_validation import validate_file
            rule = ContractStore().file_rule(job, args['input_field'])
            return validate_file(Path(args['local_path']), rule, args['experiment_data']).as_dict()
        from plugins.boltzmann.preflight import preflight_submission
        return preflight_submission(job, args['experiment_data']).as_dict()
    from sci_cli.config import load_config_readonly
    from model_tools import _select_tool_names, handle_function_call
    cfg = load_config_readonly()
    enabled = cfg.get('platform_toolsets', {}).get('cli', [])
    disabled = cfg.get('agent', {}).get('disabled_toolsets', [])
    grants = sorted(_select_tool_names(enabled, disabled, True))
    if name not in grants:
        raise ValueError('Requested connector is not granted by the owning profile')
    return handle_function_call(name, args, enabled_toolsets=enabled, disabled_toolsets=disabled,
                                enabled_tools=grants, session_id=request['session_id'],
                                user_task='Execute one assignment-admitted small-molecule connector operation through the existing owning profile')


def _worker(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', required=True)
    parser.add_argument('--host-root', type=Path, required=True)
    parser.add_argument('--owner-home', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--response', type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    started = False
    try:
        owner = args.owner_home.resolve()
        if (os.environ.get('SCI_HOME') != str(owner)
                or os.environ.get('SCI_DISABLE_LAZY_INSTALLS') != '1'
                or args.request.is_symlink() or not args.request.is_file()
                or args.response.exists() or args.response.parent.resolve() != args.request.parent.resolve()):
            raise ValueError('Invalid private owning-host launch')
        request = json.loads(args.request.read_text())
        if set(request) != {'operation', 'name', 'arguments', 'session_id'}:
            raise ValueError('Invalid transport request')
        if ((request['operation'] == 'tool' and request['name'] not in TOOLS)
                or (request['operation'] == 'validate' and request['name'] not in {'upload', 'submit'})
                or request['operation'] not in {'tool', 'validate'}
                or not isinstance(request['arguments'], dict)):
            raise ValueError('Unsupported owning-host operation')
        _clean_arguments(request['arguments'])
        started = request['operation'] == 'tool'
        result = _execute(request, args.host_root.resolve())
        _private_write(args.response, {'ok': True, 'result': result})
        return 0
    except Exception as exc:
        # Never print exception text, tool results, credential values or signed
        # references. The original request and any native logs stay private.
        if not args.response.exists():
            try:
                _private_write(args.response, {'ok': False, 'result_available': False,
                                              'error_type': type(exc).__name__,
                                              'dispatch_may_have_started': started})
            except Exception:
                pass
        return 1


if __name__ == '__main__':
    raise SystemExit(_worker())
