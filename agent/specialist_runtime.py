"""Resolve saved specialists onto the existing delegate_task lifecycle."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import logging
import re
import time

from agent.specialist_policy import SpecialistPolicy, current_policy, specialist_scope
from agent.specialist_store import Specialist, inventory, load
from sci_constants import get_sci_home

logger = logging.getLogger(__name__)
# Authoring, credential/config changes and unmanaged execution cannot be granted by selecting a skill.
BLOCKED = frozenset({"clarify", "memory", "send_message", "cronjob_manage", "skill_manage", "manage_connections"})
EXECUTION_TOOLS = frozenset({"terminal", "execute_code"})


def capture(agent, *, session_id=None, session_db=None):
    """Take one definition snapshot at agent construction, never rebuild a live conversation."""
    try:
        items, errors = inventory()
    except (ValueError, OSError) as exc:
        items, errors = {}, [str(exc)]
    agent._specialist_home = str(get_sci_home().resolve())
    agent._specialist_snapshot = {n: s for n, s in items.items() if s.enabled and not s.needs_review}
    agent._specialist_policy = current_policy()
    if session_id and session_db is not None:
        session = session_db.get_session(session_id)
        if isinstance(session, dict):
            raw = session_db.get_session_model_config_value(session_id, "saved_specialists")
            if isinstance(raw, dict):
                try:
                    restored = {n: Specialist.parse(s) for n, s in raw.items()}
                    if any(n != s.name for n, s in restored.items()):
                        raise ValueError("Saved specialist snapshot names disagree.")
                    agent._specialist_snapshot = restored
                except ValueError as exc:
                    agent._specialist_snapshot = {}
                    errors.append(str(exc))
            elif session.get("message_count", 0):
                # A conversation predating this feature had no specialist hints/schema.
                agent._specialist_snapshot = {}
    for error in errors:
        logger.warning("Specialist unavailable: %s", error)


def persist_snapshot_config(agent):
    """Use the existing session metadata and compression lineage, not a second session store."""
    agent._session_init_model_config["saved_specialists"] = {
        name: asdict(item) for name, item in agent._specialist_snapshot.items()}


def decorate(agent, *, enabled_toolsets=None, disabled_toolsets=None):
    import model_tools
    snapshot = agent._specialist_snapshot
    policy = getattr(agent, "_specialist_policy", None)
    if isinstance(policy, SpecialistPolicy):
        snapshot = {n: s for n, s in snapshot.items() if n in policy.children}
    agent._specialist_parent_tools = frozenset()
    if not snapshot:
        return
    raw = model_tools.get_tool_definitions(enabled_toolsets=enabled_toolsets, disabled_toolsets=disabled_toolsets,
                                          quiet_mode=True, skip_tool_search_assembly=True)
    agent._specialist_parent_tools = frozenset(t["function"]["name"] for t in raw)
    agent.tools = deepcopy(agent.tools)
    for tool in agent.tools:
        fn = tool["function"]
        if fn["name"] != "delegate_task":
            continue
        props = fn["parameters"]["properties"]
        props["tasks"]["items"]["properties"]["specialist"] = {
            "type": "string", "description": "Saved specialist name from action=catalog. Manual specialists require the user's explicit name in this turn."}
        props["action"]["enum"] = [*props["action"]["enum"], "catalog"]
        props["query"] = {"type": "string", "description": "Search saved specialists by name or purpose (catalog only)."}
        props["page"] = {"type": "integer", "minimum": 1, "description": "Saved specialist catalog page, starting at 1."}
        automatic = [f"{s.name}: {s.purpose[:180]}" for s in snapshot.values() if s.automatic]
        fn["description"] += (
            "\nSaved specialists are available. Use action=catalog to find names and purposes, then tasks[].specialist "
            "to run one. Delegate matching tasks to the relevant automatic specialist, including explanatory questions; "
            "automatic specialists ALSO support explicit user requests. Manual specialists require explicit user request. "
            "If a specialist is unavailable, report why; do not silently substitute unrestricted delegation.\n"
            + "Automatic specialists (first 20): " + "; ".join(automatic[:20]))


def catalog(agent, query="", page=1):
    if not isinstance(query, str) or type(page) is not int or page < 1:
        raise ValueError("Catalog query must be text and page a positive whole number.")
    snapshot = getattr(agent, "_specialist_snapshot", {})
    policy = getattr(agent, "_specialist_policy", None)
    rows = [{"name": s.name, "purpose": s.purpose, "automatic": s.automatic}
            for s in snapshot.values() if (not policy or s.name in policy.children)
            and query.casefold() in (s.name + " " + s.purpose).casefold()]
    return {"specialists": rows[(page - 1) * 20:page * 20], "page": page, "total": len(rows),
            "note": "Conversation snapshot; execution rechecks enabled state and revision. Changes need a new conversation."}


def _explicitly_requested(parent, name):
    text = getattr(parent, "_specialist_user_request", "")
    return isinstance(text, str) and re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text, re.I) is not None


def resolve(parent, task):
    """Validate every task BEFORE construction. Return None for ordinary temporary delegation."""
    owner = getattr(parent, "_specialist_policy", None)
    owner = owner if isinstance(owner, SpecialistPolicy) else None
    name = task.get("specialist")
    if not name:
        if owner:
            raise ValueError("This specialist can delegate only to its approved named children; choose tasks[].specialist.")
        return None
    if not isinstance(name, str):
        raise ValueError("specialist must be a saved name.")
    home = str(get_sci_home().resolve())
    if home != getattr(parent, "_specialist_home", None):
        raise ValueError("Specialist owner profile does not match this session. Start a conversation in the intended profile.")
    item = getattr(parent, "_specialist_snapshot", {}).get(name)
    if item is None:
        raise ValueError(f"Specialist {name} is not enabled in this conversation. Review /subagents and start /new.")
    current = load(name)
    if not current.enabled or current.needs_review or current.revision != item.revision:
        raise ValueError(f"Specialist {name} was disabled or edited. Review it and start /new; no task was submitted.")
    if owner:
        if name not in owner.children or name in owner.ancestry:
            raise ValueError("This child is not approved, or would create a delegation cycle.")
    elif not item.automatic and not _explicitly_requested(parent, name):
        raise ValueError(f"{name} requires an explicit user request naming it. Ask the user or use /subagent run.")
    forbidden = set(item.tools) & BLOCKED
    if forbidden:
        raise ValueError(f"Unsupported specialist permissions: {', '.join(sorted(forbidden))}. Review the definition.")
    allowed = set(item.tools)
    if item.skills:
        allowed |= {"skill_view", "skills_list"}
    if item.children:
        allowed.add("delegate_task")
    parent_names = getattr(parent, "_specialist_parent_tools", frozenset())
    from sci_cli.config import load_config_readonly
    from model_tools import _select_tool_names
    cfg = load_config_readonly()
    enabled = cfg.get("platform_toolsets", {}).get(getattr(parent, "platform", "cli"), getattr(parent, "enabled_toolsets", None))
    disabled = list(set(cfg.get("agent", {}).get("disabled_toolsets", [])) | set(getattr(parent, "disabled_toolsets", None) or []))
    live_names = _select_tool_names(enabled, disabled, quiet_mode=True)
    if owner and (not allowed <= owner.tools or not set(item.skills) <= owner.skills):
        raise ValueError("Child permissions exceed its pod lead's approved tools or skills.")
    missing = allowed - (parent_names & live_names)
    from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS
    helpers = set(BOLTZMANN_WORKFLOW_TOOLS)
    if allowed & helpers:
        from sci_cli.specialist_capabilities import boltzmann_ready
        if not boltzmann_ready() or not helpers <= (parent_names & live_names):
            missing |= allowed & helpers
    # Selected tools are maximum grants, not prerequisites for every informational task.
    # Missing tools never gain a handler/schema; the child must report a blocker if needed.
    allowed -= missing
    deadline = time.monotonic() + item.timeout_seconds
    if owner:
        deadline = min(deadline, owner.deadline)
    policy = SpecialistPolicy(name, home, item.revision, frozenset(allowed), frozenset(item.skills),
                              frozenset(item.children), (*owner.ancestry, name) if owner else (name,), deadline,
                              frozenset(missing))
    return item, policy


def context_for(item, task_context):
    # Do not preprocess skill templates: those can execute shell snippets or install dependencies.
    from tools.skills_tool import skill_view
    sections = [f"Saved specialist: {item.name}\nPurpose: {item.purpose}\n{item.instructions}",
                "Expected output: " + item.output,
                "Report blockers and requests for user approval to the parent. Do not bypass a refusal, "
                "switch providers, or repeat a submission with an uncertain outcome. Return evidence/artifact paths; "
                "distinguish predictions from verified findings."]
    for name in item.skills:
        result = json.loads(skill_view(name, preprocess=False, allow_setup=False))
        if not result.get("success"):
            raise ValueError(f"Selected skill {name} could not be loaded: {result.get('error', 'unavailable')}")
        sections.append(f"Skill {name}:\n" + str(result.get("content", "")))
    for reference in item.skill_files:
        name, _, path = reference.partition("#")
        result = json.loads(skill_view(name, file_path=path, preprocess=False, allow_setup=False))
        if not result.get("success"):
            raise ValueError(f"Selected skill module {reference} could not be loaded: {result.get('error', 'unavailable')}")
        sections.append(f"Selected module {reference}:\n" + str(result.get("content", "")))
    if item.sources:
        sections.append("Reference locations only; no blanket permission to upload or transmit their contents. "
                        "Use only sources approved for this assignment:\n" + "\n".join(item.sources))
    if task_context:
        sections.append("Assignment context:\n" + str(task_context))
    return "\n\n".join(sections)


def build_child(build, *, plan, **kwargs):
    if plan is None:
        return build(**kwargs)
    item, policy = plan
    kwargs["context"] = context_for(item, kwargs.get("context"))
    if policy.unavailable_tools:
        kwargs["context"] += ("\nUnavailable tools in this conversation: " + ", ".join(sorted(policy.unavailable_tools)) +
                              ". You may answer tasks that do not need these tools. If the assignment needs one, report "
                              "the missing capability to the parent; do not substitute providers or claim execution. "
                              "Boltzmann execution requires authorization in this owning profile through /add_boltzmann.")
    kwargs["max_iterations"] = min(kwargs["max_iterations"], item.max_iterations)
    with specialist_scope(policy):
        child = build(**kwargs)
    parent = kwargs["parent_agent"]
    # Named pods share a finite iteration pool; a child cannot multiply the pod's budget.
    if getattr(parent, "_specialist_policy", None):
        from agent.iteration_budget import IterationBudget
        child.iteration_budget = IterationBudget(kwargs["max_iterations"], parent=parent.iteration_budget)
    child.run_budget_seconds = max(0.01, policy.deadline - time.monotonic())
    child._specialist_snapshot = dict(getattr(parent, "_specialist_snapshot", {}))
    persist_snapshot_config(child)
    child._specialist_user_request = ""
    return child


def discard_unstarted(children, parent, reason):
    """Dispose constructed siblings when batch preparation fails before any task starts."""
    from tools.delegate_tool_child_run import _detach_child, _close_child
    from agent.specialist_runs import record
    for _, task, child in children:
        _detach_child(parent, child)
        _close_child(child, "Specialist preparation cancelled")
        try:
            record(child, task["goal"], {"status": "cancelled", "error": reason, "summary": None})
        except (OSError, ValueError):
            logger.warning("Could not save cancelled specialist receipt", exc_info=True)
