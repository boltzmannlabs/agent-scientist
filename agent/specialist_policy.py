"""Execution-time specialist grants, propagated through context-aware worker threads."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from inspect import signature
from typing import TYPE_CHECKING
import time

if TYPE_CHECKING:
    from agent.specialist_store import Specialist

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
    read_paths: tuple[str, ...] | None = None
    execution_home: str = ''
    private_tools: frozenset[str] = frozenset()
    private_skills: frozenset[str] = frozenset()
    private_toolsets: tuple[str, ...] = ()
    owner_tools: frozenset[str] = frozenset()
    owner_toolsets: tuple[str, ...] | None = None
    owner_disabled_toolsets: tuple[str, ...] = ()
    specialists: tuple[Specialist, ...] = ()
    owner_platform: str = 'cli'
    owner_multiplex: bool = False
    assignment: object = None
    artifact_hashes: tuple[tuple[str, str], ...] = ()


def owner_profile_delegation(function):
    """Resolve named descendants in their owner profile, not the lead's private home."""
    parameters = signature(function)

    @wraps(function)
    def call(*args, **kwargs):
        parent = parameters.bind_partial(*args, **kwargs).arguments.get('parent_agent')
        policy = getattr(parent, '_specialist_policy', None)
        if not isinstance(policy, SpecialistPolicy):
            return function(*args, **kwargs)
        from sci_constants import get_sci_home
        from tools.registry import tool_error
        active = str(get_sci_home().resolve())
        if active not in {policy.home, policy.execution_home} or getattr(parent, '_specialist_home', None) != policy.home:
            return tool_error('Specialist owner profile does not match this session; no child was started.')
        from agent.specialist_extensions import capability_scope
        with capability_scope(policy.home, multiplex=policy.owner_multiplex):
            return function(*args, **kwargs)
    return call


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
    if str(get_sci_home().resolve()) not in {policy.home, policy.execution_home}:
        return "Specialist profile scope changed; this tool call was stopped."
    if time.monotonic() >= policy.deadline:
        return "Specialist runtime limit reached; no further tool was executed."
    if name not in policy.tools and name not in _BRIDGES:
        return f"Tool {name} is not approved for specialist {policy.name}. Return the requirement to the parent."
    if name == "skill_view" and args.get("name") not in policy.skills:
        return "This skill is not selected for the specialist. Ask the parent to review it."
    from agent.specialist_assignment import check_arguments
    mismatch = check_arguments(name, args)
    if mismatch:
        return mismatch
    from agent.specialist_inputs import check_read
    return check_read(policy, name, args)
