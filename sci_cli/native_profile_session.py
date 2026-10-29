"""Native CLI handoff: never transplant a live agent into another profile."""

from pathlib import Path


def profile_label():
    from sci_cli.profiles import get_active_profile_name
    name = get_active_profile_name()
    return "main" if name == "default" else name


def list_profiles(ui):
    from sci_cli.profiles import list_profile_names, get_profile_dir
    from sci_cli.config import read_user_config_raw
    from sci_constants import get_sci_home
    active = get_sci_home().resolve()
    for name in list_profile_names():
        home = get_profile_dir(name)
        label = "main" if name == "default" else name
        marker = " [active]" if home.resolve() == active else ""
        try:
            config = read_user_config_raw(home / "config.yaml")
            tools = config.get("platform_toolsets", {}).get("cli")
            backend = config.get("terminal", {}).get("backend", "local")
            summary = f"{backend}; capabilities: {', '.join(tools) if isinstance(tools, list) else 'profile defaults'}"
        except (OSError, ValueError):
            summary = "configuration needs attention"
        ui.show(f"{label}{marker} — {summary}")


def request_switch(cli, name, ui):
    from sci_cli.profiles import get_profile_dir, list_profile_names, normalize_profile_name
    from sci_constants import get_sci_home
    name = "default" if name == "main" else normalize_profile_name(name)
    if name not in list_profile_names():
        raise ValueError("Unknown profile. Use /profiles_list to see available profiles.")
    if getattr(cli, "_agent_running", False) or getattr(cli, "_science_running_worker", None):
        raise ValueError("Finish or cancel the current turn before switching profiles.")
    home = get_profile_dir(name)
    if home.resolve() == get_sci_home().resolve():
        ui.show(f"Already in {'main' if name == 'default' else name}.")
        return
    app = getattr(cli, "_app", None)
    if app is None or not app.is_running:
        raise ValueError("Profile activation requires the interactive CLI.")
    from sci_cli.session_browser import flush_before_switch
    flush_before_switch(cli)
    # Startup will resolve the target's model, tools, secret scope and previous
    # conversation. No globals or toolsets of this conversation are rewritten.
    args = ["--cli", "-p", name]
    if (home / "state.db").is_file():
        from sci_state import SessionDB
        db = SessionDB(home / "state.db", read_only=True)
        try:
            sessions = db.search_sessions(source="cli", limit=1)
        finally:
            db.close()
        if sessions:
            args.extend(["--resume", sessions[0]["id"]])
    cli._pending_profile_home = str(home.resolve())
    cli._pending_relaunch = args
    ui.show(f"Switching to {'main' if name == 'default' else name}. Saving this conversation; "
            "the native CLI will resume that profile's latest conversation, or start a new one. "
            "Its retained transcript will appear in scrollback. Use /resume to choose another conversation.")
    if getattr(cli, "_background_managed", False):
        from sci_cli.background_chat_lifecycle import navigate
        navigate(cli)
        return
    cli._should_exit = True
    app.loop.call_soon_threadsafe(app.exit)


def relaunch_profile(cli):
    """Called on the main thread after normal CLI/session/terminal cleanup."""
    import os
    import subprocess
    import sys
    from tools.environments.local import served_profile_child_env
    from sci_cli._launchers import runtime_command
    home = Path(cli._pending_profile_home)
    env = served_profile_child_env(target_home=home, inherit_credentials=True)
    # These are launch identity, not target configuration. -p establishes them.
    for key in ("SCI_PROFILE", "SCI_PROFILE_NAME", "TERMINAL_CWD"):
        env.pop(key, None)
    # A viewer may have entered via python -m or PM's isolated bootstrap.
    # Resolving another `sci` on PATH can lose this install's dependencies.
    argv = runtime_command(Path(__file__).resolve().parents[1], cli._pending_relaunch, home=home)
    from sci_cli.config import read_user_config_raw
    config = read_user_config_raw(home / "config.yaml")
    workspace = home / "workspace"
    # Native science profiles own a workspace; ordinary native profiles retain
    # their explicitly configured cwd (or the launch cwd).
    if workspace.is_dir() and config.get("terminal", {}).get("backend", "local") == "local":
        os.chdir(workspace)
    if sys.platform == "win32":
        raise SystemExit(subprocess.call(argv, env=env))
    from sci_cli.observability.shared_metrics_startup import mark_in_place_relaunch
    mark_in_place_relaunch()
    os.execvpe(argv[0], argv, env)


def request_resume(cli, session_id, ui, *, foreground=False):
    """A fresh runtime re-reads current permissions, while the target keeps its cached prompt."""
    from sci_constants import get_sci_home
    from sci_cli.profiles import get_active_profile_name
    from sci_cli.session_browser import flush_before_switch
    flush_before_switch(cli)
    if session_id and session_id == cli.session_id:
        ui.show("This conversation is already open here.")
        return
    if session_id and not cli._session_db.get_session(session_id):
        raise ValueError("Conversation is not in this profile's store.")
    from sci_cli.cli_session_recovery import prepare_resume
    from sci_cli.background_chats import find_worker
    worker = find_worker(session_id) if session_id else None
    takeover = False
    if worker and worker["attached"]:
        ui.choose("Move this chat's viewer here? Its other terminal will detach; its agent keeps running.",
                  ("Cancel", "Move viewer"))
        takeover = True
    if not worker and session_id and not prepare_resume(session_id, ui):
        return
    app = cli._app
    cli._pending_profile_home = str(get_sci_home().resolve())
    cli._pending_relaunch = ["--cli", "-p", get_active_profile_name()]
    if foreground:
        cli._pending_relaunch.append("--no-daemon")
    if worker:
        cli._pending_relaunch = ["-p", get_active_profile_name(), "background", "attach", worker["id"]]
        if takeover:
            cli._pending_relaunch.append("--takeover")
    elif session_id:
        cli._pending_relaunch.extend(["--resume", session_id])
    if worker:
        ui.show("Attaching to the same running agent. Its conversation, prompt and permissions remain unchanged.")
    else:
        ui.show(f"Opening [{profile_label()}] conversation {session_id or '(new)'}. Current permissions will be re-read; "
                "saved model context remains compressed; its retained transcript will appear in scrollback.")
    if getattr(cli, "_background_managed", False):
        from sci_cli.background_chat_lifecycle import navigate
        navigate(cli)
        return
    cli._should_exit = True
    app.loop.call_soon_threadsafe(app.exit)
