"""Worker-local execution gate, independent of mutable MCP registry entries."""

import json


def install_gate(agent, ask, *, allow_local=True, external_tools=()):
    from sci_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    base = {"terminal", "read_file", "write_file", "patch", "search_files", "skill_view", "skills_list"}
    if not allow_local:
        base = {"skill_view", "skills_list"}
    # Asking the user grants no execution or data-transfer permission. The CLI
    # includes this only when an interactive question transport is available.
    base.add("clarify")
    base.update(external_tools)
    permitted = frozenset(t["function"]["name"] for t in agent.tools
                          if t["function"]["name"] in base or t["function"]["name"].startswith("mcp_"))
    # Freeze schemas once, before this conversation's first provider request.
    agent.tools = [t for t in agent.tools if t["function"]["name"] in permitted]
    agent.valid_tool_names = set(permitted)

    def gate(*, tool_name, args, next_call, **context):
        try:
            if tool_name not in permitted:
                return json.dumps({"error": "Tool is outside this profile's reviewed permissions."})
            if tool_name.startswith("mcp_") or tool_name in external_tools:
                if ask("external", tool=tool_name, arguments=args) is not True:
                    return json.dumps({"error": "External transfer/tool execution was not approved."})
            if tool_name == "terminal" and args.get("background"):
                return json.dumps({"error": "Detached background jobs are disabled in project workers."})
            if tool_name == "skill_view":
                from tools.skills_tool import skill_view
                return skill_view(args.get("name", ""), file_path=args.get("file_path"),
                                  task_id=context.get("task_id"), preprocess=False, allow_setup=False)
        except Exception:
            # Generic plugin middleware fails open on callback exceptions; this
            # security gate must return a refusal instead, including broken IPC.
            return json.dumps({"error": "Project permission check failed; execution was blocked."})
        return next_call(args)

    ctx = PluginContext(PluginManifest(name="science-profile-policy"), get_plugin_manager())
    return ctx.register_middleware("tool_execution", gate)
