"""Private JSON-lines transport for one persistent, isolated profile conversation.

Not a shell subcommand. The owning CLI supplies messages and answers permission
requests. No source-profile environment/config is copied into this interpreter.
"""

import contextlib
import json
import signal
import sys
import threading


def main():
    wire = sys.stdout
    lock = threading.Lock()

    def emit(kind, **values):
        with lock:
            wire.write(json.dumps({"kind": kind, **values}) + "\n")
            wire.flush()

    def read():
        line = sys.stdin.readline(1_000_001)
        if not line or len(line) > 1_000_000:
            raise EOFError("Profile controller disconnected or oversized request.")
        return json.loads(line)

    def ask(kind, **values):
        # Tool batches can ask concurrently; only one request may own stdin.
        with approval_lock:
            emit(kind, **values)
            return read().get("answer")

    approval_lock = threading.Lock()
    instance = None
    try:
        # The scoped child environment intentionally strips Sci's PYTHONPATH.
        # A managed launcher uses a bare Python, so bind its dependencies before
        # importing config (ruamel) or any other third-party package. Keep boot
        # diagnostics off the JSON-lines control channel.
        with contextlib.redirect_stdout(sys.stderr):
            import sci_bootstrap  # noqa: F401

        from sci_constants import get_sci_home
        from sci_cli.native_profile_runtime import routing_spec, build_native_cli
        from sci_cli.science_profiles import MANIFEST
        home = get_sci_home()
        legacy = (home / MANIFEST).is_file()
        spec = routing_spec(home)
        # Setup chatter goes to stderr, never into the framed control channel.
        with contextlib.redirect_stdout(sys.stderr):
            from cli import SciCLI
            toolsets = (["skills"] if spec.setup_pending else ["terminal", "file", "skills"]) + list(spec.mcp_tools)
            instance = (SciCLI(toolsets=toolsets, max_turns=30, run_budget=spec.max_seconds, ignore_rules=True)
                        if legacy else build_native_cli(home, spec))
            instance._clarify_callback = lambda questions: ask("clarify", questions=questions)
            instance._approval_callback = lambda command, description, *a, **kw: (
                "once" if ask("approval", command=command, description=description) is True else "deny")
            instance._secret_capture_callback = lambda *a, **kw: None
            instance._sudo_password_callback = lambda *a, **kw: None
            instance._science_permission_ask = ask
            if not instance._init_agent():
                raise RuntimeError("Profile model initialization failed. Check the shared provider login.")
            agent = instance.agent
            def interrupt(signum, frame):
                from agent.interrupt_compat import request_hard_interrupt
                request_hard_interrupt(agent, "Profile controller interrupted execution")
                raise KeyboardInterrupt()
            signal.signal(signal.SIGTERM, interrupt)
            signal.signal(signal.SIGINT, interrupt)
        emit("ready", profile=spec.name, session=instance.session_id)
        while True:
            request = read()
            if request.get("kind") == "close":
                break
            if request.get("kind") != "turn" or not isinstance(request.get("text"), str):
                raise ValueError("Malformed profile request.")
            with contextlib.redirect_stdout(sys.stderr):
                routing_spec(home)
                if legacy:
                    from sci_cli.science_profile_cli_policy import prepare
                    prepare(instance)
                try:
                    result = agent.run_conversation(request["text"], conversation_history=instance.conversation_history,
                                                    task_id=instance.session_id)
                finally:
                    # Shell children cannot outlive a finished project turn. The
                    # next turn gets a clean container with the same output mount.
                    from tools.terminal_tool import cleanup_all_environments
                    cleanup_all_environments()
            if result.get("messages"):
                instance.conversation_history = result["messages"]
            emit("result", text=result.get("final_response", ""), session=agent.session_id,
                 failed=bool(result.get("failed") or result.get("partial") or result.get("interrupted") or result.get("completed") is False))
    except (EOFError, KeyboardInterrupt):
        emit("stopped", message="Profile worker stopped. No work continues in this worker.")
    except Exception as exc:
        emit("error", message=f"{type(exc).__name__}: {exc}")
    finally:
        if instance is not None and instance.agent is not None:
            with contextlib.redirect_stdout(sys.stderr):
                try:
                    instance.agent.close()
                finally:
                    from tools.terminal_tool import cleanup_all_environments
                    cleanup_all_environments()


if __name__ == "__main__":
    main()
