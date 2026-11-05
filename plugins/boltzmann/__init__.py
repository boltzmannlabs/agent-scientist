"""Agent Scientist's bundled, credential-gated Boltzmann connector."""

import json
from functools import partial

from .auth import available
from .schemas import SCHEMAS
from . import tools


def _call(handler, args, **kwargs):
    try:
        result = handler(**args)
        if handler.__name__ in {"handle_boltzmann_submit", "handle_boltzmann_status"}:
            from gateway.session_context import get_session_env
            from .job_monitor import monitor_result
            result = monitor_result(handler.__name__.removeprefix("handle_"), args, result,
                                    session_id=kwargs.get("session_id") or get_session_env("SCI_SESSION_ID"))
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception:
        # HTTP exception strings may include signed URLs or credential-bearing data.
        return json.dumps({"error": "Boltzmann operation failed. Check service connectivity and supplied parameters; no success is confirmed."})


def register(ctx):
    from .job_monitor import register_cli as jobs_cli, command, observe, session_start, session_context
    from .job_continuation import checkpoint, guard
    ctx.register_cli_command(name="boltzmann-jobs", help="Inspect, stop or resume durable Boltzmann job monitoring",
                             setup_fn=jobs_cli, handler_fn=command)
    for name, callback in {"post_tool_call": observe, "pre_api_request": checkpoint,
                           "pre_tool_call": guard, "on_session_start": session_start,
                           "pre_llm_call": session_context}.items():
        ctx.register_hook(name, callback)
    from .receipt_cli import register_cli, receipt_command
    ctx.register_cli_command(name="boltzmann-receipts", help="Inspect or safely clean profile-local upload receipts",
                             setup_fn=register_cli, handler_fn=receipt_command)
    from .execution_policy import render_execution_policy
    from .onboarding import register_skills
    ctx.register_system_prompt_section("boltzmann.execution", render_execution_policy,
                                       max_chars=3500)
    if available():
        register_skills(ctx)
    for schema in SCHEMAS:
        ctx.register_tool(name=schema["name"], toolset="boltzmann", schema=schema,
                          handler=partial(_call, getattr(tools, "handle_" + schema["name"])),
                          check_fn=available, description=schema.get("description", ""))
