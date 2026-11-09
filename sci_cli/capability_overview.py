"""Profile inventory from local metadata and the existing conversation; never probes."""

from dataclasses import dataclass
import shlex


_SECTIONS = {
    "Tools": {"tool"},
    "Skills": {"skill"},
    "MCP connections": {"MCP", "default MCP"},
    "Plugins": {"plugin"},
    "Service providers": {"provider"},
}
_PAGE_SIZE = 8


@dataclass(frozen=True)
class Capability:
    kind: str
    name: str
    enabled: bool | None
    in_session: bool | None = None
    detail: str = ""
    pending: bool = False
    installed: bool = True

    @property
    def summary(self):
        if self.kind == "default MCP":
            return "Setup available"
        if self.pending:
            return "Pending new conversation"
        if not self.installed:
            return "Setup required"
        if self.in_session is True:
            return "In conversation" if self.enabled is not False else "In conversation; disabled in settings"
        if self.enabled is None:
            return "Provider setting"
        return "Enabled" if self.enabled else "Disabled"

    @property
    def description(self):
        if self.kind == "default MCP":
            return "Not configured. No permissions granted.\n" + self.detail
        enabled = {None: "Not verified; managed by provider settings", True: "Enabled", False: "Disabled"}[self.enabled]
        current = {None: "Not verified", True: "Listed", False: "Not listed"}[self.in_session]
        pending = "\nActivation: pending a new conversation" if self.pending else ""
        installation = "Configured/installed" if self.installed else "Missing; saved configuration only"
        return (f"Installation: {installation}\nProfile: {enabled}\n"
                f"Conversation: {current}{pending}\n{self.detail}")


def inventory(cli):
    from sci_constants import get_sci_home
    from sci_cli.config import load_config_readonly
    from sci_cli.plugins_discovery import collect_directory_manifests, resolve_manifest_winners
    from sci_cli.science_integrations import missing_defaults
    from sci_cli.tools_config import _get_platform_tools
    from sci_cli.profile_input_dialogs import interactive_toolsets
    from agent.skill_utils import iter_skill_index_files, get_disabled_skill_names, parse_config_string_list
    from model_tools import _select_tool_names
    from tools.registry import registry
    cfg = load_config_readonly()
    agent = getattr(cli, "agent", None)
    live = {t.get("function", {}).get("name") for t in getattr(agent, "tools", []) or []}
    selected, excluded = interactive_toolsets(
        sorted(_get_platform_tools(cfg, "cli")),
        parse_config_string_list(cfg.get("agent", {}).get("disabled_toolsets", [])))
    selected_names = _select_tool_names(selected, excluded, quiet_mode=True)
    rows = []

    for name in registry.get_all_tool_names():
        entry = registry.get_entry(name)
        if entry:
            current = name in live if agent and "tool_search" not in live else (True if name in live else None)
            detail = ("Built-in interactive input dialogs. No setup required. Start a new conversation if this session predates the update."
                      if name == "clarify" else "Deferred tools require discovery; dependencies and readiness not probed.")
            rows.append(Capability("tool", name, name in selected_names, current, detail))
    for name, value in cfg.get("mcp_servers", {}).items():
        if not isinstance(value, dict):
            continue
        enabled = value.get("enabled", True) and name not in excluded and name in selected
        allowlist = value.get("tools", {})
        detail = "Connection/authentication not probed. " + (
            f"Explicit allowlist: {len(allowlist['include'])} entries." if "include" in allowlist
            else "No explicit allowlist; review permissions.")
        rows.append(Capability("MCP", name, enabled, detail=detail,
                               pending=name in getattr(cli, "_science_deferred_mcp", {})))
    plugins = cfg.get("plugins", {})
    manifests = resolve_manifest_winners(collect_directory_manifests())
    from agent.secret_scope import build_profile_secret_scope
    secrets = build_profile_secret_scope(get_sci_home())
    for name in sorted(set(manifests) | set(plugins.get("enabled", []))):
        manifest = manifests.get(name)
        enabled = (name in plugins.get("enabled", []) and name not in plugins.get("disabled", []) and
                   name not in excluded)
        kind = "plugin"
        detail = "Plugin-wide permissions; dependencies/authentication not verified."
        if manifest is None:
            detail = "Configured plugin installation/manifest is missing; setup required."
        elif manifest.kind != "standalone":
            enabled, kind = None, "provider"
            detail = "Category-managed integration; consult its provider/backend configuration."
        else:
            required = [item if isinstance(item, str) else item.get("name", "") for item in manifest.requires_env]
            missing = [key for key in required if key and not secrets.get(key)]
            if missing:
                detail += " Missing credential/environment slots: " + ", ".join(missing) + "."
        if name == "boltzmann":
            from sci_cli.science_catalog_view import authorization_summary
            detail = (authorization_summary() + "\nScientific inventory: /boltzmann_tools. "
                      "Inspect request schemas through tool discovery; this view does not test live execution.")
        visible = True if manifest and set(manifest.provides_tools) & live else None
        rows.append(Capability(kind, name, enabled, visible, detail, installed=manifest is not None))
    disabled = get_disabled_skill_names("cli")
    home = get_sci_home()
    for path in iter_skill_index_files(home / "skills", "SKILL.md"):
        name = path.parent.relative_to(home / "skills").as_posix()
        from sci_cli.science_profiles_catalog import skill_identifiers
        rows.append(Capability("skill", name, not skill_identifiers(name, path.parent) & disabled,
                               detail="Saved instructions; this conversation's cached skill index is not refreshed."))
    for name in missing_defaults(cfg):
        rows.append(Capability("default MCP", name, False,
                               detail="Choose Set up missing defaults to review setup and permissions."))
    return sorted(rows, key=lambda r: (r.kind, r.name))


def _browse(ui, rows, profile, section, query=""):
    page = 0
    while True:
        matches = [r for r in rows if (section == "All" or r.kind in _SECTIONS[section])
                   and query.casefold() in f"{r.kind} {r.name} {r.summary} {r.description}".casefold()]
        pages = max(1, (len(matches) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        page = min(page, pages - 1)
        entries = {f"{r.name} [{r.kind}] — {r.summary}": r
                   for r in matches[page * _PAGE_SIZE:(page + 1) * _PAGE_SIZE]}
        controls = ["Search", "Back", "Done"]
        if query:
            controls.append("Clear search")
        if page + 1 < pages:
            controls.append("Next page")
        if page:
            controls.append("Previous page")
        if any(r.kind == "default MCP" for r in matches):
            controls.append("Set up missing defaults")
        title = f"Capabilities [{profile}] · {section}\n{len(matches)} entries · page {page + 1}/{pages}"
        if query:
            title += f" · search: {query}"
        title += "\nSelect an entry for details. Enabled does not confirm service readiness."
        if not matches:
            title += "\nNo matches. Search again, clear the search, or go Back."
        choice = ui.choose(title, [*entries, *controls])
        if choice in entries:
            row = entries[choice]
            actions = ["Back", "Done"]
            if row.kind == "default MCP":
                actions.insert(0, "Set up missing defaults")
            action = ui.choose(f"{row.name} · {row.kind}\n{row.description}", actions)
            if action != "Back":
                return action
            continue
        if choice in {"Back", "Done", "Set up missing defaults"}:
            return choice
        if choice == "Search":
            query, page = ui.ask(f"Search {section.lower()} by name or status:"), 0
            continue
        page, query = {
            "Clear search": (0, ""),
            "Next page": (page + 1, query),
            "Previous page": (page - 1, query),
        }[choice]


def run(cli, command, ui=None):
    from sci_cli.skill_add import WizardUI, Cancelled
    from sci_cli.native_profile_session import profile_label
    ui = ui or WizardUI(cli, numbered_choices=False)
    setup_started = False
    try:
        args = shlex.split(command)[1:]
        if args == ["setup"]:
            setup_started = True
            from sci_cli.science_integrations import setup_defaults
            return setup_defaults(cli, ui)
        query = " ".join(args[1:] if args[:1] == ["search"] else args)
        rows, profile = inventory(cli), profile_label()
        section = "All" if args else None
        while True:
            if section is None:
                sections = {f"{name} ({sum(r.kind in kinds for r in rows)})": name
                            for name, kinds in _SECTIONS.items()}
                actions = [*sections, f"All ({len(rows)})", "Search", "Done"]
                if any(r.kind == "default MCP" for r in rows):
                    actions.insert(-1, "Set up missing defaults")
                choice = ui.choose(f"Capabilities [{profile}]\nChoose a category. Local metadata only; no service is contacted.", actions)
                if choice in {"Done", "Set up missing defaults"}:
                    action = choice
                else:
                    section = sections.get(choice, "All")
                    query = ui.ask("Search all capabilities by name or status:") if choice == "Search" else ""
                    action = _browse(ui, rows, profile, section, query)
            else:
                action = _browse(ui, rows, profile, section, query)
            if action == "Done":
                ui.show("Capabilities closed. Nothing changed.")
                return
            if action == "Set up missing defaults":
                setup_started = True
                from sci_cli.science_integrations import setup_defaults
                return setup_defaults(cli, ui)
            section, query = None, ""
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Setup cancelled. Separately approved downloads may remain." if setup_started
                else "Capabilities closed. Nothing changed.")
    except Exception:
        ui.show("Capability setup could not complete. Approved installations may remain; existing conversation unchanged."
                if setup_started else "Capabilities could not be read. No settings changed.")
