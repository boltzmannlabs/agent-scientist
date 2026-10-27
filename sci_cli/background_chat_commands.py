"""Shell/slash entrypoints; task ownership stays profile-local."""

import json
import os
import shlex

from sci_cli.background_chats import ensure_server, find_worker, read_server, request


def build_parser(subparsers):
    parser = subparsers.add_parser("background", help="Persistent CLI chats: start, attach, status, stop")
    parser.add_argument("action", nargs="?", default="status", choices=("start", "attach", "status", "stop", "shutdown"))
    parser.add_argument("session", nargs="?", help="Saved session ID (start) or background chat/session ID (attach/stop)")
    parser.add_argument("--detach", action="store_true", help="Start without attaching this terminal")
    parser.add_argument("--takeover", action="store_true", help="Move the attached viewer here; keep the same agent")
    parser.add_argument("--force", action="store_true", help="Force-stop a stuck worker; unsaved output may be lost")
    parser.add_argument("--json", action="store_true", help="Print status/control results as JSON")
    parser.set_defaults(func=command)


def show_status(result, emit=print):
    if not result["chats"]:
        emit("No background chats in this profile.")
    for row in result["chats"]:
        emit(f"{row['id']} | session {row.get('session_id') or '(starting)'} | {row['state']} | "
             f"{'attached' if row['attached'] else 'detached'} | local background tasks: {row['background_tasks']}")


def attach_on_resume(cli):
    """A live managed chat is attached, never killed/rebuilt by ordinary resume."""
    if not getattr(cli, "_resumed", False):
        return False
    import sys
    from sci_cli.background_chat_terminal import attach
    from sci_cli.cli_session_recovery import StartupRecoveryUI
    from sci_cli.skill_add import Cancelled
    try:
        worker = find_worker(cli.session_id)
        if not worker or worker["pid"] == os.getpid():
            return False
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            cli._console_print("This chat has a background worker. Attach from an interactive terminal.")
            return True
        ui = StartupRecoveryUI()
        if worker["attached"]:
            ui.choose("Move the viewer here? Work continues; the previous terminal will detach.",
                      ("Cancel", "Move viewer"))
        attach(worker["id"], takeover=worker["attached"])
    except (Cancelled, KeyboardInterrupt, EOFError):
        cli._console_print("Attachment cancelled. The background chat is unchanged.")
    except (OSError, ValueError, RuntimeError) as exc:
        cli._console_print(f"Could not attach to background chat: {exc}. No duplicate worker was started.")
    return True


def _start(args):
    from sci_cli.background_chat_terminal import attach
    from sci_cli.background_chats import terminal_environment
    if args.json and not args.detach:
        raise ValueError("Use --detach with --json when starting a background chat.")
    ensure_server()
    size = os.get_terminal_size() if os.isatty(1) else os.terminal_size((100, 30))
    result = request("start", session_id=args.session, cwd=os.getcwd(), cols=size.columns, rows=size.lines,
                     terminal_env=terminal_environment())
    if args.json:
        print(json.dumps(result))
    else:
        print(f"Background chat: {result['id']}. Terminal closure will detach; the local worker can continue.")
    if not args.detach:
        attach(result["id"], takeover=args.takeover)


def _status(args):
    if read_server():
        result = request("status")
        print(json.dumps(result)) if args.json else show_status(result)
        return
    from sci_cli.background_chats import locations
    _, root, _ = locations()
    saved = json.loads((root / "chats.json").read_text(encoding="utf-8-sig")) if (root / "chats.json").exists() else {"chats": []}
    result = {"running": False, "previous_chats": saved["chats"], "previous_status_stale": True}
    if args.json:
        print(json.dumps(result))
    else:
        print("Background service is not running. No work will be automatically restarted.")
        for row in saved["chats"]:
            print(f"Saved session: {row.get('session_id') or row['id']} — previous runtime status is stale.")


def _attach(args):
    from sci_cli.background_chat_terminal import attach
    if not args.session:
        raise ValueError("Use sci background attach <chat-or-session-id>.")
    worker = find_worker(args.session)
    if not worker:
        raise ValueError("No live worker for that chat. Resume its saved conversation normally.")
    attach(worker["id"], takeover=args.takeover)


def _control(args):
    result = request(args.action, id=args.session, force=args.force)
    print(json.dumps(result) if args.json else result.get("message") or result["state"])


def command(args):
    try:
        {"start": _start, "status": _status, "attach": _attach,
         "stop": _control, "shutdown": _control}[args.action](args)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Background chat operation stopped: {exc}")
        return 1


def _slash_detach(cli, ui, parts):
    from sci_cli.background_chats import detach_cli
    if not detach_cli(cli):
        ui.show("This is an ordinary foreground chat. Use /background while idle first. "
                "Your task has not been interrupted and no command was queued.")


def _slash_status(cli, ui, parts):
    if read_server():
        show_status(request("status"), ui.show)
    else:
        ui.show("No background service is running in this profile.")


def _slash_stop(cli, ui, parts):
    if len(parts) != 3:
        raise ValueError("Use /background stop <chat-or-session-id>.")
    ui.show("Stopping interrupts the local chat. Already submitted remote jobs may continue.")
    if ui.choose("Stop this background chat?", ("Cancel", "Stop chat")) == "Stop chat":
        worker = find_worker(parts[2])
        if not worker:
            raise ValueError("No live background chat matches that ID.")
        ui.show(request("stop", id=worker["id"])["message"])


def dispatch_while_busy(cli, text, *, has_images=False):
    """Transport controls must not sit behind the very turn being detached."""
    if has_images or not getattr(cli, "_agent_running", False) or not text.strip():
        return False
    if text.strip().lower() in ("/exit", "/quit") and getattr(cli, "_background_managed", False):
        from sci_cli.background_chats import detach_cli
        detach_cli(cli)
        return True
    if text.split(None, 1)[0].lower() not in ("/background", "/detach"):
        return False
    slash(cli, text)
    return True


def slash(cli, text):
    from sci_cli.skill_add import WizardUI, Cancelled
    from sci_cli.session_browser import flush_before_switch
    from sci_cli.profiles import get_active_profile_name
    from sci_constants import get_sci_home
    ui = WizardUI(cli)
    try:
        parts = shlex.split(text)
        action = parts[1].lower() if len(parts) > 1 else "start"
        if parts[0].lower() == "/detach":
            action = "detach"
        managed = getattr(cli, "_background_managed", False)
        if managed and action == "start":
            _slash_detach(cli, ui, parts)
            return
        if getattr(cli, "_agent_running", False) and action not in ("detach", "status"):
            guidance = (
                "Detach with Ctrl+] before switching chats; use `sci background stop <id>` in your shell to stop one."
                if managed else
                "An ordinary running chat cannot be moved into background mode. "
                "Let this task finish, then use /background before starting the next task; "
                "or start a separate chat from your shell with `sci background start`. "
                "Ctrl+Z pauses an ordinary chat; it does not keep the task running.")
            ui.show("Your task is still running and has not been interrupted. This command was not queued. " + guidance)
            return
        handler = {"detach": _slash_detach, "status": _slash_status, "stop": _slash_stop}.get(action)
        if handler:
            handler(cli, ui, parts)
            return
        if action not in ("start", "attach"):
            raise ValueError("Use /background [status|attach <id>|stop <id>] or /detach.")
        if getattr(cli, "_background_managed", False):
            raise ValueError("Already using a persistent worker. Use /resume to switch chats or /activate to switch profiles.")
        flush_before_switch(cli)
        if getattr(cli, "_background_tasks", None):
            raise ValueError("Wait for local /bg tasks before moving this foreground chat.")
        if action == "attach" and len(parts) != 3:
            raise ValueError("Use /background attach <chat-or-session-id>.")
        ui.show("Background mode keeps this profile's CLI running after terminal disconnection. "
                "Its normal permissions still apply; unanswered approval prompts may time out. "
                "Use Ctrl+], /detach, or /exit to disconnect; background stop ends the worker.")
        if ui.choose("Enable or attach persistent background mode?", ("Cancel", "Continue")) != "Continue":
            return
        args = ["-p", get_active_profile_name(), "background", action]
        if action == "attach":
            worker = find_worker(parts[2])
            if not worker:
                raise ValueError("No live worker matches this ID.")
            args.append(worker["id"])
            if worker["attached"]:
                ui.choose("Move the viewer here? The other viewer will disconnect; work continues.", ("Cancel", "Move viewer"))
                args.append("--takeover")
        elif cli._session_db and cli._session_db.get_session(cli.session_id):
            args.append(cli.session_id)
        cli._pending_profile_home = str(get_sci_home().resolve())
        cli._pending_relaunch = args
        cli._should_exit = True
        cli._app.loop.call_soon_threadsafe(cli._app.exit)
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Background operation cancelled; current chat unchanged.")
    except (OSError, ValueError, RuntimeError) as exc:
        ui.show(f"Background operation stopped: {exc}")
