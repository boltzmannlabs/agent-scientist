"""Run an actual script in an explicit, isolated existing SDK environment.

This embedding launcher does not install/activate packages, resolve credentials,
copy profiles, or execute scientific requests. The interpreter must already be
prepared through the owning SDK's supported package manager. Its normal bootstrap
still activates any committed dependency selection. Supported lazy provisioning
is disabled so merely importing the SDK cannot trigger an application update.
"""
from pathlib import Path
import os
import subprocess


def launch_spec(*, host_root, interpreter, sci_home, script, arguments=(), environment=None):
    """Return argv/env for a file-based SDK launch, never stdin or shell source."""
    root = Path(host_root).expanduser().resolve()
    python = Path(interpreter).expanduser().absolute()
    home = Path(sci_home).expanduser().resolve()
    source = Path(script).expanduser().resolve()
    if not (root / "run_agent.py").is_file() or not (root / "pm").is_dir():
        raise ValueError("An existing Agent Scientist SDK checkout is required")
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError("An existing PM-prepared executable interpreter is required")
    if not home.is_dir() or home == (Path.home() / ".sci").resolve():
        raise ValueError("Choose an existing isolated SCI_HOME, separate from the default profile")
    if not source.is_file() or source.suffix != ".py":
        raise ValueError("An existing Python script file is required; stdin and -c are unsupported")
    if not all(isinstance(value, str) for value in arguments):
        raise ValueError("Script arguments must be text")
    env = dict(os.environ if environment is None else environment)
    for key in ("__SCI_ACTIVATED", "__SCI_TEST_PYTHON", "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(key, None)
    env.update({"SCI_HOME": str(home), "SCI_RUNTIME_DIR": str(home / "tools"),
                "SCI_DISABLE_LAZY_INSTALLS": "1", "PYTHONPATH": str(root),
                "PYTHONDONTWRITEBYTECODE": "1"})
    return [str(python), "-B", str(source), *arguments], env


def run_script(*, timeout_seconds=180, **options):
    """Run the selected script without a shell; return captured private output.

    A timeout terminates this local process, not any remote scientific job.
    Callers own its receipts and should never infer nonacceptance from a timeout.
    """
    if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
        raise ValueError("A positive timeout is required")
    command, env = launch_spec(**options)
    return subprocess.run(command, env=env, cwd=str(Path(options["script"]).resolve().parent),
                          capture_output=True, text=True, timeout=timeout_seconds, check=False)
