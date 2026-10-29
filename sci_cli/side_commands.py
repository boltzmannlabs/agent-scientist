"""Classic CLI side-chat routing. Parent identity and input queue never change."""

import time
from contextlib import nullcontext

from agent.memory_provider import spawn_context_thread
from agent.side_conversation import SideConversation
from sci_constants import sci_home_key
from sci_cli.side_surface import begin_turn, configure_agent, end_turn, output_scope, release_callbacks, tool_output_scope


def _show(cli, text):
    view = getattr(cli, "_side_view", None)
    controller = getattr(cli, "_side_controller", None)
    if view is not None and controller and not controller.conversation.closed.is_set():
        view.append(text)
        return
    from sci_cli.skill_add import WizardUI
    with output_scope(None):
        WizardUI(cli).show(text)
    app = getattr(cli, "_app", None)
    if app is not None:
        app.invalidate()


def active(cli):
    controller = getattr(cli, "_side_controller", None)
    return bool(controller and controller.active and not controller.conversation.closed.is_set())


class SideController:
    def __init__(self, cli):
        self.cli = cli
        self.owner = (sci_home_key(), cli.session_id)
        self.ui = getattr(getattr(cli, "_side_view", None), "surface", None)
        if self.ui is not None:
            self.ui.agent = None
            self.ui.conversation_history = []
        self.conversation = SideConversation(cli.agent, cli.conversation_history,
                                             configure=lambda agent: configure_agent(self, agent))
        self.active = True
        self.running = False
        self.started = 0.0
        self.outcome = "ready"
        self.worker = None

    def select(self, selected):
        self.active = selected
        view = getattr(self.cli, "_side_view", None)
        if view is not None:
            view.select(selected)

    def emit(self, text):
        if not self.conversation.closed.is_set():
            _show(self.cli, text)

    def submit(self, question, images=None):
        if self.running:
            self.emit("Still working. Your message was not sent; wait for this turn to finish.")
            return False
        self.running = True
        self.started = time.monotonic()
        self.outcome = "working"
        view = getattr(self.cli, "_side_view", None)
        if view is not None:
            view.follow = True

        def run():
            capture = tool_output_scope(self.emit) if self.ui is not None else nullcontext()
            with output_scope(self.emit), capture:
                try:
                    message = begin_turn(self, question, images or [])
                    answer = self.conversation.answer(message)
                    if not self.conversation.closed.is_set():
                        self.outcome = "ready"
                        end_turn(self, answer)
                except Exception:
                    from cli import logger
                    logger.exception("Side conversation failed")
                    if not self.conversation.closed.is_set():
                        self.outcome = "failed"
                        self.emit("This request stopped with an error. No automatic retry was made. "
                                  "Main is unchanged; check SCI logs before retrying an external action.")
                finally:
                    release_callbacks(self.ui)
                    self.running = False
                    if self.conversation.closed.is_set():
                        self.outcome = "closed"
                    app = getattr(self.cli, "_app", None)
                    if app is not None:
                        app.invalidate()

        self.worker = spawn_context_thread(target=run, name="sci-side-conversation", daemon=True)
        self.worker.start()
        return True

    def close(self):
        # Release only side-owned questions. A parent approval may still be waiting.
        if self.ui is not None:
            with output_scope(self.emit):
                self.ui._clear_active_overlays_for_interrupt()
        self.conversation.close()
        self.select(False)
        view = getattr(self.cli, "_side_view", None)
        if view is not None:
            view.clear()
        self.outcome = "stopping" if self.running else "closed"


def current(cli):
    cli = getattr(cli, "_side_owner", cli)
    controller = getattr(cli, "_side_controller", None)
    owner = (sci_home_key(), cli.session_id)
    if controller and controller.owner != owner:
        # Parent compaction rotates the physical session row without changing the
        # conversation. Keep the captured side context; /new and /resume still close it.
        db = getattr(cli, "_session_db", None)
        if (controller.owner[0] == owner[0] and controller.conversation.parent is cli.agent and db
                and db.resolve_resume_session_id(controller.owner[1]) == cli.session_id):
            controller.owner = owner
            return controller
        controller.close()
        cli._side_controller = None
        return None
    return controller


def handle_side(cli, command, *, images=None):
    cli = getattr(cli, "_side_owner", cli)
    parts = command.split(None, 1)
    arg = parts[1].strip() if len(parts) > 1 else ""
    controller = current(cli)
    if controller and controller.conversation.closed.is_set():
        if controller.running:
            _show(cli, "Previous side request is still stopping. Wait before opening another.")
            return False
        controller = None
    if controller is None:
        if not getattr(cli, "agent", None):
            # Resume preloads history but deliberately leaves runtime creation lazy.
            # The command worker initializes it without sending a synthetic main turn.
            if not cli._init_agent():
                return False
        controller = cli._side_controller = SideController(cli)
        view = getattr(cli, "_side_view", None)
        if view is not None:
            view.clear()
        controller.select(True)
    else:
        controller.select(True)
    if arg:
        return controller.submit(arg, images)
    if images and controller.ui is not None:
        controller.ui._attached_images.extend(images)
    return True


def toggle(cli):
    """Switch only the view and input owner; neither agent receives an interrupt."""
    controller = current(cli)
    if controller and not controller.conversation.closed.is_set():
        controller.select(not controller.active)
    elif not getattr(cli, "agent", None):
        # Authentication/discovery may need terminal modals; never block the UI loop.
        cli._pending_input.put("/side")
    else:
        handle_side(cli, "/side")


def route_input(cli, text, *, has_images=False):
    """Side messages never enter the parent's queue, slash dispatcher or transcript."""
    owner = getattr(cli, "_side_owner", cli)
    controller = current(owner)
    word = text.split(None, 1)[0].lower() if text.strip() else ""
    if word == "/side":
        if not getattr(owner, "agent", None):
            return False  # Let the ordinary command worker initialize the runtime.
        images = list(getattr(cli, "_attached_images", []))
        if getattr(cli, "_side_surface", False) and text.strip().lower() == "/side":
            images = []  # The existing side composer already owns these attachments.
        if handle_side(owner, text, images=images) and images:
            # Opening without a question transfers the attachment to side's composer.
            cli._attached_images.clear()
        return True
    if not controller or not controller.active:
        return False
    if word.startswith(("/", "!")):
        controller.emit("Switch to main with Ctrl+/ for conversation-management or shell commands. "
                        "You can ask me to use tools here normally.")
    elif text.strip() or has_images:
        images = list(getattr(cli, "_attached_images", []))
        if controller.submit(text, images):
            if hasattr(cli, "_attached_images"):
                cli._attached_images.clear()
    return True


def label(cli):
    controller = getattr(cli, "_side_controller", None)
    if not controller or controller.conversation.closed.is_set():
        return ""
    parent = "waiting for input" if any(getattr(cli, key, None) for key in (
        "_approval_state", "_clarify_state", "_secret_state", "_sudo_state")) else (
        "running" if getattr(cli, "_agent_running", False) else "idle")
    if not controller.active:
        return "Ctrl+/ side"
    return f"Side · main {parent} · Ctrl+/ switch · Ctrl+C close"


def cancel_from_keyboard(cli, event):
    controller = current(cli)
    if not controller or not controller.active:
        return False
    controller.close()
    event.app.invalidate()
    return True


def shutdown(cli):
    controller = getattr(cli, "_side_controller", None)
    if controller and not controller.conversation.closed.is_set():
        controller.close()
