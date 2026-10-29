"""Profile-local picker metadata and complete integration packages for specialists."""
import json

from agent.specialist_runtime import BLOCKED
from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS

BOLTZMANN_PACKAGE = "Boltzmann job tools"


def boltzmann_ready():
    from plugins.boltzmann.auth import available
    return available()  # local key + owning profile receipt only; no network validation


def choices(cli):
    from tools.registry import registry
    from tools.skills_tool import _find_all_skills, _is_skill_disabled
    from sci_cli.plugins import get_plugin_manager
    from model_tools import _select_tool_names
    from sci_cli.config import load_config_readonly
    cfg = load_config_readonly()
    agent = getattr(cli, "agent", None)
    enabled = getattr(agent, "enabled_toolsets", None) if agent else cfg.get("platform_toolsets", {}).get("cli", ["sci-cli"])
    disabled = getattr(agent, "disabled_toolsets", None) if agent else cfg.get("agent", {}).get("disabled_toolsets", [])
    names = _select_tool_names(enabled, disabled, quiet_mode=True)
    if agent is not None:
        # This snapshot contains deferred tools as well as immediately visible model tools.
        snapshot = getattr(agent, "_specialist_parent_tools", None)
        if snapshot:
            names &= set(snapshot)
    if not boltzmann_ready():
        names -= set(BOLTZMANN_WORKFLOW_TOOLS)
    tool_choices = {name: str(entry.schema.get("description", "No description"))
                    for name in sorted(names - BLOCKED - {"delegate_task", "skill_view", "skills_list"})
                    if (entry := registry.get_entry(name)) is not None}
    rows = _find_all_skills() + get_plugin_manager().list_plugin_skill_metadata()
    skills = {r["name"]: str(r.get("description", "")) for r in rows if not _is_skill_disabled(r["name"])}
    return skills, tool_choices


def modules():
    """Read maintained module metadata beside the winning installed plugin's contracts."""
    from sci_cli.science_catalog_view import registry_path
    path = registry_path()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {}
    for module in data.get("modules", []):
        relative = str(module.get("path", ""))
        source = (path.parent / relative).resolve()
        if not source.is_relative_to(path.parent.resolve()) or not source.is_file():
            continue
        reference = "boltzmann:tools#references/" + relative
        label = f"Boltzmann / {module['domain']} / {module['title']}"
        description = " ".join(module.get("intents", [])) or module['title']
        result[label] = (reference, description)
    return result


def skill_menu(skills, tools, item):
    """Expose module choices without copying or generating scientific instructions."""
    options = dict(skills)
    selected = list(item.skills)
    resources = {}
    if 'boltzmann:tools' in skills and set(BOLTZMANN_WORKFLOW_TOOLS) <= set(tools) and boltzmann_ready():
        for label, (reference, description) in modules().items():
            options[label] = description
            resources[label] = reference
            if reference in item.skill_files:
                selected.append(label)
        options["boltzmann:tools"] = "Common platform instructions. Choose specific scientific modules below; selecting a module includes these basics."
        if item.skill_files:
            selected = [name for name in selected if name != "boltzmann:tools"]
    # Retain unavailable or renamed module selections for review; never silently drop them.
    for reference in item.skill_files:
        if reference not in resources.values():
            resources[reference] = reference
            options[reference] = "Previously selected module; unavailable in this profile's current catalog. Review or remove it."
            selected.append(reference)
    return options, selected, resources


def tool_menu(tools, selected):
    tools, selected = dict(tools), set(selected)
    helpers = set(BOLTZMANN_WORKFLOW_TOOLS)
    ready = helpers <= set(tools) and boltzmann_ready()
    options = {k: v for k, v in tools.items() if k not in helpers}
    if ready or selected & helpers:
        options = {BOLTZMANN_PACKAGE: ("Complete upload, submit, status, download and diagnostic operations."
                                     if ready else "Unavailable here; use /add_boltzmann in this profile. No job access until authorized."),
                   **options}
    picked = [BOLTZMANN_PACKAGE] if selected & helpers else []
    return options, [*picked, *sorted(selected - helpers)]


def expand_tools(selected):
    return tuple(sorted({tool for name in selected for tool in
                         (BOLTZMANN_WORKFLOW_TOOLS if name == BOLTZMANN_PACKAGE else (name,))}))
