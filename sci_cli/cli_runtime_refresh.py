"""Refresh classic CLI runtimes at explicit conversation/attachment boundaries."""

from pathlib import Path
import os

import psutil


def fresh_conversation(cli, title=None):
    """Use the same fresh-process path as profile updates, not an in-place tool reset."""
    from sci_cli.native_profile_session import request_resume
    from sci_cli.skill_add import WizardUI
    ui = WizardUI(cli)
    if getattr(cli, '_agent_running', False):
        ui.show('Finish or cancel the current turn before starting a new conversation.')
        return
    if not getattr(cli, '_background_managed', False):
        from tools.process_registry import process_registry
        from tools.delegate_tool_registry import _active_subagents, _active_subagents_lock
        with _active_subagents_lock:
            children = bool(_active_subagents)
        if children or process_registry.count_running() or getattr(cli, '_background_tasks', {}):
            ui.show('This foreground CLI still owns background work. Finish or explicitly stop it before '
                    'starting a fresh runtime. No work was stopped or restarted.')
            return
    session_id = None
    if title:
        from sci_cli.main import _create_titled_session
        session_id = _create_titled_session(title)
        if session_id is None:
            ui.show('Could not create the named conversation. The current conversation is unchanged.')
            return
    ui.show('Starting a fresh runtime for this profile. Saved configuration, tools and code will be reloaded. '
            'The departing conversation remains saved; background jobs are not resubmitted.')
    request_resume(cli, session_id, ui, foreground=not getattr(cli, '_background_managed', False))


def newer_source(started, root=None):
    """Detect edited Python sources, including uncommitted changes, since worker startup.

    Source timestamps also work for ZIP installs and legacy workers without a build
    receipt. This is a conservative refresh notice, never permission to kill a worker.
    """
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    paths = list(root.glob('*.py'))
    for package in root.iterdir():
        if package.name.startswith('.') or not (package / '__init__.py').is_file():
            continue
        if package.name in ('tests', 'evals'):
            continue
        for directory, children, files in os.walk(package):
            children[:] = [n for n in children if not n.startswith('.') and n not in ('__pycache__', 'node_modules', 'tests')]
            paths.extend(Path(directory) / name for name in files if name.endswith('.py'))
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue  # An update may replace a file during the scan.
        # Process creation times can use a whole-second boot epoch (psutil on
        # Linux). Allow that precision window rather than flag every fresh CLI.
        if max(stat.st_mtime, stat.st_ctime) > started + 2:
            return path.relative_to(root)
    return None


def refresh_attached_worker(worker, *, home=None, ui=None):
    """Offer reviewed stop/resume when attaching to code loaded before a source edit."""
    from sci_cli.background_chats import find_worker, request, terminal_environment
    from sci_cli.cli_session_recovery import StartupRecoveryUI, prepare_resume
    from sci_cli.skill_add import Cancelled
    ui = ui or StartupRecoveryUI()
    try:
        process = psutil.Process(worker['pid'])
        changed = newer_source(process.create_time())
    except psutil.NoSuchProcess:
        return worker  # Normal attachment reports the vanished worker.
    if changed is None:
        return worker
    ui.show(f'Application source changed since this chat started ({changed}). '
            'Reconnecting alone keeps the old loaded code. Reloading requires closing its existing runtime; '
            'saved conversation history is retained, and no request is automatically rerun.')
    choice = ui.choose('Which runtime should open?',
                       ['Reload saved conversation with updated code', 'Keep existing runtime', 'Cancel'])
    if choice == 'Keep existing runtime':
        return worker
    if choice == 'Cancel':
        raise Cancelled()
    session_id = worker.get('session_id')
    if not session_id:
        raise ValueError('This worker has not saved a conversation yet. Wait for startup before refreshing.')
    cwd = process.cwd()
    # Existing recovery checks PID identity, reviews interruption of local work,
    # waits for exit and leaves the normal session lease checks in force.
    if not prepare_resume(session_id, ui, registry_home=home):
        raise Cancelled()
    if find_worker(worker['id'], home=home):
        raise ValueError('The previous worker is still alive. No replacement was started; check background status.')
    result = request('start', home=home, session_id=session_id, cwd=cwd,
                     terminal_env=terminal_environment())
    replacement = find_worker(result['id'], home=home)
    if replacement is None:
        raise ValueError('Replacement runtime exited during startup. The saved conversation is retained.')
    return replacement
