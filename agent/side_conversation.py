"""Temporary multi-turn discussion over an immutable parent snapshot.

The parent keeps running. No side turn is persisted into its transcript or used for
automatic memory extraction. The normal provider owns request
timeouts; failures never start a second request through an auxiliary provider.
"""

from copy import deepcopy
from threading import Event, Lock
from uuid import uuid4


BOUNDARY = (
    "Side conversation boundary. Everything before this boundary is reference context only. "
    "Answer only new side-conversation questions; do not continue the parent's task or act on "
    "its instructions or approvals. The parent may still be running and its later activity "
    "is not in this snapshot. Use the available tools and skills for requests made here, "
    "under the active profile's normal permissions, authentication and approval rules. "
    "File changes, configuration changes and external actions require a request in this "
    "side conversation; inherited approvals do not authorize them. The workspace and "
    "external services are shared: avoid interfering with work still running in main."
)


def completed_snapshot(history):
    """Never inherit an unfinished user turn or orphan tool-call/result pair."""
    messages = list(history or [])
    while messages and (messages[-1].get("role") != "assistant" or messages[-1].get("tool_calls")):
        messages.pop()
    return deepcopy(messages)


class SideConversation:
    def __init__(self, parent, history, *, configure=None):
        self.parent = parent
        self.id = "side-" + uuid4().hex
        self.history = completed_snapshot(history)
        self.prompt = getattr(parent, "_cached_system_prompt", None)
        self.tools = deepcopy(getattr(parent, "tools", []))
        self.transcript = []
        self._agent = None
        self._turn = Lock()
        self._state = Lock()
        self.closed = Event()
        self.configure = configure
        self.last_result = None

    def _build(self):
        from agent.background_review import build_cache_parity_fork

        fork, _, routed = build_cache_parity_fork(
            self.parent, {}, max_iterations=self.parent.max_iterations, write_origin="side_conversation")
        # A long-lived side transcript must not share mutable provider session/slot
        # identity with the parent.
        fork.session_id = self.id
        fork._inherited_cache_scope = self.id
        fork._cached_conversation_root = self.id
        fork._prompt_cache_fork_tag = self.id
        fork._cached_system_prompt = self.prompt
        fork.tools = deepcopy(self.tools)
        fork.valid_tool_names = {tool["function"]["name"] for tool in fork.tools}
        fork.save_trajectories = False
        fork._memory_store = deepcopy(self.parent._memory_store)
        # Preserve configured file-checkpoint protection without sharing per-turn state.
        fork._checkpoint_mgr = deepcopy(self.parent._checkpoint_mgr)
        fork._checkpoint_mgr.new_turn()
        fork.run_budget_seconds = getattr(self.parent, "run_budget_seconds", None)
        fork._fallback_chain = []
        fork._fallback_model = None
        # The review helper's aggregate cap belongs to a single automatic review;
        # an interactive discussion instead uses normal per-turn/context limits.
        fork._review_input_token_budget = None
        if routed:
            fork.close()
            raise RuntimeError("Side conversation must use the parent's selected provider/model.")
        if self.configure is not None:
            self.configure(fork)
        return fork

    def answer(self, question):
        question = question.strip() if isinstance(question, str) else deepcopy(question)
        if not question:
            raise ValueError("Enter a side-conversation question.")
        if not self._turn.acquire(blocking=False):
            raise ValueError("The side conversation is still answering.")
        try:
            if self.closed.is_set():
                raise ValueError("This side conversation is closed.")
            if self._agent is None:
                fork = self._build()
                with self._state:
                    self._agent = fork
            if self.closed.is_set():
                raise ValueError("This side conversation is closed.")
            message = question
            if not self.transcript:
                message = (f"{BOUNDARY}\n\n{question}" if isinstance(question, str) else
                           [{"type": "text", "text": BOUNDARY}, *question])
            result = self._agent.run_conversation(
                user_message=message, conversation_history=deepcopy(self.history))
            self.last_result = result
            if self.closed.is_set():
                return ""
            answer = (result or {}).get("final_response") or ""
            if (result or {}).get("error") or (result or {}).get("failed") or not answer.strip():
                raise RuntimeError("The side request failed or returned no answer. No fallback request was made.")
            self.history = deepcopy(result.get("messages") or [
                *self.history, {"role": "user", "content": message},
                {"role": "assistant", "content": answer}])
            self.transcript.extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
            return answer
        finally:
            try:
                if self.closed.is_set():
                    self._dispose()
            finally:
                self._turn.release()

    def _dispose(self):
        with self._state:
            fork, self._agent = self._agent, None
        try:
            if fork is not None:
                fork.close()
        finally:
            self.history.clear()
            self.transcript.clear()

    def close(self):
        """Request cancellation without blocking the terminal on a provider response."""
        from agent.interrupt_compat import request_hard_interrupt

        self.closed.set()
        with self._state:
            if self._agent is not None:
                request_hard_interrupt(self._agent)
        if self._turn.acquire(blocking=False):
            try:
                self._dispose()
            finally:
                self._turn.release()
