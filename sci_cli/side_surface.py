"""Reuse normal CLI rendering and modals with a side conversation's own UI state."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from types import SimpleNamespace
import time
import io
import threading


_output_sink = ContextVar("side_output_sink", default=None)


class _ToolOutput(io.TextIOBase):
    """Turn fragmented print()/stderr writes into side transcript lines."""

    def __init__(self, emit):
        self.emit = emit
        self.pending = {}
        self.lock = threading.RLock()

    def write(self, text):
        with self.lock:
            ident = threading.get_ident()
            parts = (self.pending.pop(ident, "") + text.replace("\r", "\n")).split("\n")
            self.pending[ident] = parts.pop()
            for line in parts:
                self.emit(line)
        return len(text)

    def flush(self):
        with self.lock:
            pending, self.pending = self.pending, {}
            for text in pending.values():
                if text:
                    self.emit(text)


@contextmanager
def tool_output_scope(emit):
    from agent.thread_scoped_output import context_scoped_output
    with context_scoped_output(_ToolOutput(emit), _ToolOutput(emit)):
        yield


@contextmanager
def output_scope(sink):
    token = _output_sink.set(sink)
    try:
        yield
    finally:
        _output_sink.reset(token)


def emit_side_output(text):
    sink = _output_sink.get()
    if sink is None:
        return False
    sink(text)
    return True


def create_surface(parent):
    # Configuration is the same, but no mutable conversation, modal, queue or stream
    # state is shared. Avoid the CLI constructor: it opens stores and runs startup.
    ui = copy(parent)
    ui._init_ui_state()
    ui._reset_stream_state()
    ui._side_surface = True
    ui._side_owner = parent
    ui._side_controller = ui._side_view = None
    ui._session_db = ui.agent = None
    ui.conversation_history = []
    ui._connection_state = None
    ui._legacy_science_gate = None
    ui._tool_callbacks_installed = False
    ui._turn_summary_collector = None
    ui._subagent_monitor = ui._subagent_dock_widget = None
    ui._held_status_lines = []
    ui._pending_edit_snapshots = {}
    ui._streamed_text_this_turn = ""
    ui._prompt_start_time = None
    ui._prompt_duration = 0.0
    ui._last_invalidate = None
    ui._interactive_turn = False
    return ui


def configure_agent(controller, agent):
    ui = controller.ui
    if ui is None:
        return
    ui.agent = agent
    ui.session_id = agent.session_id
    # Wrapping each callback also covers calls dispatched by tool-pool workers.
    def wrapped(fn):
        def callback(*args, **kwargs):
            with output_scope(controller.emit):
                return fn(*args, **kwargs)
        return callback
    callbacks = {
        "clarify_callback": ui._clarify_callback,
        "connection_callback": ui._connection_callback,
        "tool_progress_callback": ui._on_tool_progress,
        "thinking_callback": ui._on_thinking,
        "status_callback": ui._agent_status_print,
        "notice_callback": ui._on_notice,
        "notice_clear_callback": ui._on_notice_clear,
    }
    if ui.streaming_enabled:
        callbacks.update(stream_delta_callback=ui._stream_delta, tool_gen_callback=ui._on_tool_gen_start)
    if ui._inline_diffs_enabled:
        callbacks.update(tool_start_callback=ui._on_tool_start, tool_complete_callback=ui._on_tool_complete)
    if ui.show_reasoning:
        callbacks["reasoning_callback"] = ui._current_reasoning_callback()
    for name, callback in callbacks.items():
        if callback is not None:
            setattr(agent, name, wrapped(callback))
    agent.suppress_status_output = False
    agent._print_fn = wrapped(ui._agent_status_print)


def begin_turn(controller, question, images):
    ui = controller.ui
    if ui is None:
        return question
    from sci_cli.science_profile_cli_policy import prepare
    prepare(ui)  # Recheck the saved environment and permissions on every side turn.
    ui._tool_callbacks_installed = False  # callback slots are local to this turn's thread
    ui._install_tool_callbacks()
    ui._reset_stream_state()
    ui._streamed_text_this_turn = ""
    ui._agent_running = True
    ui._prompt_start_time = time.time()
    ui._print_user_message_preview(question)
    return ui._chat_route_images(question, images)


def end_turn(controller, answer):
    ui = controller.ui
    if ui is None:
        controller.emit(answer)
        return
    ui._flush_stream()
    turn = SimpleNamespace(result=controller.conversation.last_result, use_streaming_tts=False, box_opened=False)
    ui._chat_print_response_panel(turn, answer)
    ui.conversation_history = controller.conversation.history


def release_callbacks(ui):
    if ui is None:
        return
    from tools.terminal_tool import set_approval_callback, set_sudo_password_callback
    from tools.skills_tool import set_secret_capture_callback
    from agent.vault_backends.unlock import set_code_prompt_callback, set_save_login_prompt_callback, set_unlock_prompt_callback
    for setter in (set_approval_callback, set_sudo_password_callback, set_secret_capture_callback,
                   set_code_prompt_callback, set_save_login_prompt_callback, set_unlock_prompt_callback):
        setter(None)
    ui._agent_running = False
    ui._spinner_text = ""
    if ui._prompt_start_time is not None:
        ui._prompt_duration = max(0.0, time.time() - ui._prompt_start_time)
        ui._prompt_start_time = None
