"""Execution-time specialist grants, propagated through context-aware worker threads."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import time

_BRIDGES = frozenset({"tool_search", "tool_describe", "tool_call"})
_SCOPE = ContextVar("sci_specialist_policy", default=None)


@dataclass(frozen=True)
class SpecialistPolicy:
    name: str
    home: str
    revision: str
    tools: frozenset[str]
    skills: frozenset[str]
    children: frozenset[str]
    ancestry: tuple[str, ...]
    deadline: float
    unavailable_tools: frozenset[str] = frozenset()


@contextmanager
def specialist_scope(policy):
    token = _SCOPE.set(policy)
    try:
        yield
    finally:
        _SCOPE.reset(token)


def current_policy():
    return _SCOPE.get()


def filter_tools(names):
    policy = current_policy()
    return set(names) if policy is None else set(names) & policy.tools


def check_call(name, args):
    policy = current_policy()
    if policy is None:
        return None
    from sci_constants import get_sci_home
    if str(get_sci_home().resolve()) != policy.home:
        return "Specialist profile scope changed; this tool call was stopped."
    if time.monotonic() >= policy.deadline:
        return "Specialist runtime limit reached; no further tool was executed."
    if name not in policy.tools and name not in _BRIDGES:
        return f"Tool {name} is not approved for specialist {policy.name}. Return the requirement to the parent."
    if name == "skill_view" and args.get("name") not in policy.skills:
        return "This skill is not selected for the specialist. Ask the parent to review it."
    return None
