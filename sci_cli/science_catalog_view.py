"""Read-only scientific inventory shared by CLI catalog views and skill guidance."""

import json
import shlex
from collections import Counter
from pathlib import Path


_SECTIONS = {
    "Protein Engineering": {"Protein Engineering"},
    "Small Molecule Design": {"Small Molecule Design"},
    "Synthetic Chemistry": {"Synthetic Chemistry"},
    "RNA Design": {"RNA Design"},
    "Simulation tools": {"Density Functional Theory", "Molecular Dynamics", "Physics Simulation", "Simulation tools"},
}
_PAGE_SIZE = 12


def _normalized(value):
    return " ".join(value.casefold().replace("-", " ").replace("_", " ").split())


def _section(row):
    return next((name for name, domains in _SECTIONS.items() if row["domain"] in domains), row["domain"])


def registry_path():
    from sci_cli.plugins_discovery import collect_directory_manifests, resolve_manifest_winners
    manifests = resolve_manifest_winners(collect_directory_manifests())
    manifest = manifests.get("boltzmann")
    root = Path(manifest.path) if manifest else Path(__file__).resolve().parents[1] / "plugins/boltzmann"
    refs = root / "skills/boltzmann-tools/references"
    canonical = refs / "tool-contracts.v1.json"
    # Older separately installed plugins have not necessarily been migrated yet.
    if canonical.is_file() and json.loads(canonical.read_text(encoding="utf-8-sig")).get("status") == "canonical":
        return canonical
    return refs / "module-registry.v1.json"


def catalog_rows(path=None, *, domain="", query=""):
    data = json.loads((path or registry_path()).read_text(encoding="utf-8-sig"))
    modules = {m["id"]: m for m in data["modules"]}
    rows = []
    tools = list(data["tools"].values()) if isinstance(data["tools"], dict) else data["tools"]
    for tool in [*tools, *data.get("unavailable_entries", [])]:
        if tool.get("status") in {"removed", "ignored"}:
            continue
        module = modules.get(tool.get("module_id"), {})
        row = {"domain": module.get("domain", "Unassigned"),
               "module": module.get("title", "Unassigned"), "name": tool["display_name"],
               "status": tool.get("status", "unknown")}
        searchable = " ".join([*row.values(), *tool.get("aliases", [])]).casefold()
        if domain.casefold() not in (row["domain"] + " " + row["module"]).casefold():
            continue
        if query.casefold() not in searchable:
            continue
        rows.append(row)
    return sorted(rows, key=lambda r: (r["status"] != "active", r["domain"], r["module"], r["name"]))


def authorization_summary():
    from plugins.boltzmann.auth import available
    from sci_cli.config import load_config_readonly
    from sci_constants import get_sci_home
    cfg = load_config_readonly()
    plugins = cfg.get("plugins", {})
    disabled = set(plugins.get("disabled", [])) | set(cfg.get("agent", {}).get("disabled_toolsets", []))
    selected = cfg.get("platform_toolsets", {}).get("cli")
    restricted = ("boltzmann" not in plugins.get("enabled", []) or "boltzmann" in disabled or
                  (selected is not None and "boltzmann" not in selected))
    legacy = (get_sci_home() / "science-profile.json").is_file()
    return ("Local authorization: " + ("present" if available() else "missing; use /add_boltzmann") +
            "; profile access: " + ("restricted/not selected" if restricted else "configured; execution gates still apply") +
            ("; legacy isolation policy applies" if legacy else "") +
            ". Catalog visibility is not execution permission, live entitlement, or readiness verification.")


def _filtered_rows(section, query, domain):
    rows = catalog_rows(domain=domain)
    if query:
        matches = catalog_rows(domain=domain, query=query)
        normalized = _normalized(query)
        rows = [row for row in rows if row in matches or (normalized and normalized in _normalized(_section(row)))]
    if section != "All":
        rows = [row for row in rows if _section(row) == section]
    return sorted(rows, key=lambda row: (row["status"] != "active", _section(row), row["module"], row["name"]))


def _tool_choices(rows, section):
    labels = []
    for row in rows:
        group = f"{_section(row)} → {row['module']}" if section == "All" else row["module"]
        label = f"{group} → {row['name']}"
        if row["status"] != "active":
            label += f" [{row['status']}]"
        labels.append(label)
    # Some distinct backend entries share a display name. Keep both selectable.
    counts, seen = Counter(labels), Counter()
    choices = {}
    for label, row in zip(labels, rows):
        seen[label] += 1
        key = f"{label} (entry {seen[label]})" if counts[label] > 1 else label
        choices[key] = row
    return choices


def _browse_tools(ui, section, query="", domain=""):
    page = 0
    while True:
        rows = _filtered_rows(section, query, domain)
        pages = max(1, (len(rows) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        page = min(page, pages - 1)
        entries = list(_tool_choices(rows, section).items())[page * _PAGE_SIZE:(page + 1) * _PAGE_SIZE]
        choices = dict(entries)
        controls = ["Search", "Back", "Done"]
        if query or domain:
            controls.append("Clear search")
        if page + 1 < pages:
            controls.append("Next page")
        if page:
            controls.append("Previous page")
        title = f"{section} — {len(rows)} tools; page {page + 1}/{pages}"
        if query:
            title += f"; search: {query}"
        if domain:
            title += f"; module filter: {domain}"
        if not rows:
            title += "\nNo matching tools. Search again, clear the search, or go Back."
        choice = ui.choose(title + "\nSelect a tool to view its catalog details; no tool will run.",
                           [*controls, *choices])
        if choice in {"Back", "Done"}:
            return choice
        if choice in choices:
            row = choices[choice]
            detail = (f"{row['name']}\nModule: {_section(row)} → {row['module']}\n"
                      f"Catalog status: {row['status']}\nCatalog details only; no tool has run or been enabled.")
            if ui.choose(detail, ["Back", "Done"]) == "Done":
                return "Done"
            continue
        if choice == "Search":
            query, page = ui.ask(f"Search {section} tools, aliases, or modules:"), 0
            continue
        page, query, domain = {
            "Clear search": (0, "", ""),
            "Next page": (page + 1, query, domain),
            "Previous page": (page - 1, query, domain),
        }[choice]


def run_catalog(cli, command, ui=None):
    from sci_cli.skill_add import WizardUI, Cancelled
    ui = ui or WizardUI(cli)
    try:
        args = shlex.split(command)[1:]
        section, query, domain = None, "", ""
        if args and args[0].casefold() == "search":
            section, query = "All", " ".join(args[1:])
        elif args:
            requested = " ".join(args)
            section = next((name for name in [*_SECTIONS, "All"] if _normalized(name) == _normalized(requested)), "All")
            domain = "" if _normalized(requested) == _normalized(section) else requested
        ui.show(authorization_summary())
        while True:
            if section is None:
                choice = ui.choose("Boltzmann scientific tools — choose a module", [*_SECTIONS, "All", "Search", "Done"])
                if choice == "Done":
                    break
                section = "All" if choice == "Search" else choice
                query = ui.ask("Search all scientific tools, aliases, or modules:") if choice == "Search" else ""
            if _browse_tools(ui, section, query, domain) == "Done":
                break
            section, query, domain = None, "", ""
        ui.show("Catalog closed. Nothing changed.")
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Catalog closed. Nothing changed.")
    except (ValueError, OSError, KeyError):
        ui.show("The installed Boltzmann catalog could not be read. No permissions changed.")
