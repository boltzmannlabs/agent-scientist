"""Normal interactive launches attach to a profile's persistent CLI owner."""

import argparse
import os
import sys


def worker_arguments(args):
    """Serialize parsed chat options using the parser's own flag definitions."""
    from sci_cli._parser import build_top_level_parser
    _, _, chat = build_top_level_parser()
    skipped = {"help", "cli", "tui", "tui_dev", "tui_native", "no_daemon",
               "resume", "continue_last", "in_dir", "no_restore_cwd"}
    result = ["--cli", "--no-daemon", "--no-restore-cwd", "chat"]
    for action in chat._actions:
        value = getattr(args, action.dest, None)
        if action.dest in skipped or value is None or value is False:
            continue
        flag = next((s for s in action.option_strings if s.startswith("--")), None)
        if not flag:
            raise ValueError(f"Cannot preserve chat option: {action.dest}")
        if isinstance(action, argparse._StoreTrueAction):
            result.append(flag)
        elif isinstance(action, argparse._AppendAction):
            result.extend(f"{flag}={item}" for item in value)
        else:
            result.append(f"{flag}={value}")
    return result


def service_eligible(args, *, use_tui=False):
    return (not use_tui and os.name == "posix"
            and getattr(args, "command", None) in (None, "chat")
            and not getattr(args, "no_daemon", False)
            and sys.stdin.isatty() and sys.stdout.isatty()
            and getattr(args, "query_file", None) != "-"
            and not getattr(args, "oneshot", None)
            and not getattr(args, "oneshot_exit", False) and not getattr(args, "quiet", False)
            and not getattr(args, "safe_mode", False) and not getattr(args, "ignore_user_config", False)
            and (getattr(args, "output_format", None) or "text") == "text")


def launch_interactive(args, *, use_tui=False):
    """Return True only if this call owned the client lifecycle (including errors)."""
    if not service_eligible(args, use_tui=use_tui):
        return False
    from sci_cli.background_chats import ensure_server, find_worker, request, terminal_environment
    from sci_cli.background_chat_terminal import attach
    from sci_cli.cli_session_recovery import StartupRecoveryUI, prepare_resume
    from sci_cli.skill_add import Cancelled
    try:
        session_id = getattr(args, "resume", None)
        worker = find_worker(session_id) if session_id else None
        ui = StartupRecoveryUI()
        takeover = bool(worker and worker["attached"])
        if takeover:
            ui.choose("Move the viewer here? The same task continues; the other terminal disconnects.",
                      ("Cancel", "Move viewer"))
        if not worker:
            if session_id and not prepare_resume(session_id, ui):
                return True
            ensure_server()
            size = os.get_terminal_size()
            worker = request("start", session_id=session_id, cwd=os.getcwd(),
                             cols=size.columns, rows=size.lines, launch_args=worker_arguments(args),
                             terminal_env=terminal_environment())
        attach(worker["id"], takeover=takeover)
    except (Cancelled, KeyboardInterrupt, EOFError):
        print("Connection cancelled. No task was restarted.")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Cannot connect to this chat: {exc}\nNo duplicate task was started. "
              "Use `sci background status` to inspect it. `sci --no-daemon` starts a foreground chat.")
        raise SystemExit(1) from None
    return True
